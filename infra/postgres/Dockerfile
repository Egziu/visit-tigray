# PostgreSQL 16 + PostGIS 3.4 + pgvector, with no apt at build time.
# pgvector is copied from the official pgvector image; both images derive from the official
# Debian postgres:16 base, so the extension is ABI-compatible with this server major version.
FROM pgvector/pgvector:0.8.0-pg16 AS pgvector

FROM postgis/postgis:16-3.4
COPY --from=pgvector /usr/lib/postgresql/16/lib/vector.so /usr/lib/postgresql/16/lib/
COPY --from=pgvector /usr/share/postgresql/16/extension/vector* /usr/share/postgresql/16/extension/
COPY init/ /docker-entrypoint-initdb.d/
COPY vt-entrypoint.sh /usr/local/bin/vt-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/vt-entrypoint.sh"]
CMD ["postgres"]
