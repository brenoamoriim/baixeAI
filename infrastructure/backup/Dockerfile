# Backup runner: same pg_dump major version as the database, plus age (encryption) and rclone (off-site copy).
FROM postgres:17.11-alpine
RUN apk add --no-cache age=1.3.2-r1 rclone=1.74.1-r3
COPY backup.sh /usr/local/bin/backup.sh
RUN chmod 755 /usr/local/bin/backup.sh && mkdir -p /backups && chown postgres:postgres /backups
USER postgres
ENTRYPOINT ["/usr/local/bin/backup.sh"]
CMD ["loop"]
