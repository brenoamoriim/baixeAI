#!/bin/sh
# Encrypted PostgreSQL backups.
#   backup.sh once   -> one backup now
#   backup.sh loop   -> one backup every BACKUP_INTERVAL_SECONDS (default 1 day)
# The dump is encrypted with an age PUBLIC key (BACKUP_AGE_RECIPIENT): this server can create backups but
# cannot read them. The private key stays with the partners (password manager), never on the VM.
set -eu

DIR=/backups
KEEP_DAYS=${BACKUP_KEEP_DAYS:-14}

backup_once() {
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  out="$DIR/baixeai-$stamp.dump.age"
  # custom format (-Fc): compressed, restorable table by table with pg_restore
  pg_dump -Fc --no-owner --no-privileges | age -r "$BACKUP_AGE_RECIPIENT" -o "$out.partial"
  mv "$out.partial" "$out"
  size=$(wc -c < "$out")
  [ "$size" -gt 1024 ] || { echo "{\"level\":\"ERROR\",\"msg\":\"backup too small\",\"file\":\"$out\"}"; exit 1; }
  echo "{\"level\":\"INFO\",\"msg\":\"backup ok\",\"file\":\"$(basename "$out")\",\"bytes\":$size}"
  find "$DIR" -name 'baixeai-*.dump.age' -mtime +"$KEEP_DAYS" -delete
  if [ -n "${RCLONE_REMOTE:-}" ]; then
    rclone copy "$out" "$RCLONE_REMOTE" --s3-no-check-bucket \
      && echo "{\"level\":\"INFO\",\"msg\":\"backup copied off-site\",\"remote\":\"$RCLONE_REMOTE\"}" \
      || echo "{\"level\":\"ERROR\",\"msg\":\"off-site copy failed\"}"
  fi
}

case "${1:-loop}" in
  once) backup_once ;;
  loop)
    while true; do
      backup_once || echo "{\"level\":\"ERROR\",\"msg\":\"backup failed\"}"
      sleep "${BACKUP_INTERVAL_SECONDS:-86400}"
    done
    ;;
  *) echo "usage: backup.sh once|loop" >&2; exit 2 ;;
esac
