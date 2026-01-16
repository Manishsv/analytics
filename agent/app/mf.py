import json
import os
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Dict, Any


@dataclass
class MFResult:
    stdout: str
    stderr: str
    returncode: int


class MetricFlowClient:
    """
    Thin wrapper around the `mf` CLI.
    This keeps the service LLM-agnostic and enforces guardrails before executing anything.
    """

    def __init__(self, dbt_project_dir: str, profiles_dir: str):
        self.dbt_project_dir = os.path.abspath(dbt_project_dir)
        self.profiles_dir = os.path.abspath(profiles_dir)
        # Find mf command at initialization
        import shutil
        import sys
        
        # Strategy 1: Try shutil.which with current PATH
        mf_path = shutil.which("mf")
        if mf_path and os.path.exists(mf_path):
            self.mf_cmd = mf_path
        else:
            # Strategy 2: Check venv bin directory relative to Python executable
            python_dir = os.path.dirname(sys.executable)
            venv_mf = os.path.join(python_dir, "mf")
            if os.path.exists(venv_mf):
                self.mf_cmd = venv_mf
            else:
                # Strategy 3: Check common venv locations relative to project
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                for venv_name in [".venv310", ".venv", "venv"]:
                    venv_mf_path = os.path.join(project_root, venv_name, "bin", "mf")
                    if os.path.exists(venv_mf_path):
                        self.mf_cmd = venv_mf_path
                        break
                else:
                    # Last resort: try mf in PATH (will fail if not found)
                    self.mf_cmd = "mf"

    def _run(self, args: List[str], timeout_s: int = 30) -> MFResult:
        cmd = [self.mf_cmd, *args]
        env = os.environ.copy()
        env["DBT_PROFILES_DIR"] = self.profiles_dir
        # Ensure PATH includes the directory containing mf
        if os.path.dirname(self.mf_cmd) not in env.get("PATH", "").split(os.pathsep):
            mf_dir = os.path.dirname(self.mf_cmd)
            if "PATH" in env:
                env["PATH"] = f"{mf_dir}{os.pathsep}{env['PATH']}"
            else:
                env["PATH"] = mf_dir
        proc = subprocess.run(
            cmd,
            cwd=self.dbt_project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
            env=env,
        )
        return MFResult(proc.stdout, proc.stderr, proc.returncode)

    def list_metrics_and_dimensions(self) -> Dict[str, Any]:
        """
        Uses `mf list metrics` and `mf list dimensions`.
        Output formats vary slightly across versions; we return raw text plus best-effort parsing.
        Note: `mf list dimensions` requires a metric, so we use the first available metric.
        """
        metrics = self._run(["list", "metrics"], timeout_s=30)

        if metrics.returncode != 0:
            raise RuntimeError(f"mf list metrics failed: {metrics.stderr.strip()}")

        # Extract first metric name for dimensions listing
        # Format: "• metric_name: ..." or similar
        first_metric = None
        for line in metrics.stdout.split('\n'):
            if '•' in line and ':' in line:
                first_metric = line.split('•')[1].split(':')[0].strip()
                break

        dims_output = ""
        if first_metric:
            dims = self._run(["list", "dimensions", "--metrics", first_metric], timeout_s=30)
            if dims.returncode == 0:
                dims_output = dims.stdout
            # If dimensions listing fails, we still return metrics

        return {
            "metrics_raw": metrics.stdout,
            "dimensions_raw": dims_output,
        }

    def query(
        self,
        metrics: List[str],
        dimensions: Optional[List[str]] = None,
        where: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 200,
        timeout_s: int = 60,
    ) -> MFResult:
        """
        Executes a MetricFlow query with guardrails.
        - metrics: required list
        - dimensions: optional list
        - where: optional MetricFlow where clause (kept simple; validate upstream)
        - start_time/end_time: optional; format depends on your semantic time configuration
        - limit: row limit guardrail
        """
        if not metrics:
            raise ValueError("At least one metric is required.")

        # Guardrails
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000.")

        args = ["query", "--metrics", ",".join(metrics), "--limit", str(limit)]

        if dimensions:
            args += ["--group-by", ",".join(dimensions)]

        if where:
            # Keep this conservative; do not allow arbitrary injection.
            # Best practice: translate structured filters to where clauses, don't accept raw.
            args += ["--where", where]

        if start_time:
            args += ["--start-time", start_time]
        if end_time:
            args += ["--end-time", end_time]

        return self._run(args, timeout_s=timeout_s)
