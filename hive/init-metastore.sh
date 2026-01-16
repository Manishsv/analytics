#!/bin/sh
set -e

# Copy metastore-site.xml template to writable location and substitute environment variables
cp /opt/hive/conf/metastore-site.xml.template /tmp/metastore-site.xml
sed -i "s|\${POSTGRES_DB}|${POSTGRES_DB}|g" /tmp/metastore-site.xml
sed -i "s|\${POSTGRES_USER}|${POSTGRES_USER}|g" /tmp/metastore-site.xml
sed -i "s|\${POSTGRES_PASSWORD}|${POSTGRES_PASSWORD}|g" /tmp/metastore-site.xml
sed -i "s|\${MINIO_ROOT_USER}|${MINIO_ROOT_USER}|g" /tmp/metastore-site.xml
sed -i "s|\${MINIO_ROOT_PASSWORD}|${MINIO_ROOT_PASSWORD}|g" /tmp/metastore-site.xml
cp /tmp/metastore-site.xml /opt/hive/conf/metastore-site.xml

# Initialize schema if needed (with explicit PostgreSQL connection properties)
/opt/hive/bin/schematool \
  -dbType postgres \
  -initSchema \
  -verbose \
  -userName ${POSTGRES_USER} \
  -passWord ${POSTGRES_PASSWORD} \
  -url "jdbc:postgresql://postgres:5432/${POSTGRES_DB}" \
  || true

# Start metastore
exec /opt/hive/bin/hive --service metastore
