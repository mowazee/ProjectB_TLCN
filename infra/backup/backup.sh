#!/bin/sh
# Sao lưu / khôi phục tự động (NFR-03, GUIDE mục 6.4). Chạy trong container "backup"/"restore" của compose.yaml
# (image postgres:18-alpine: có pg_dump/pg_restore/psql cùng phiên bản với server).
#
#   backup.sh daemon          chạy mãi: mỗi ngày lúc BACKUP_AT (giờ UTC; mặc định 19:30 UTC = 02:30 giờ Việt Nam)
#   backup.sh run [nhãn]      sao lưu ngay: database + storage -> /backups/<thời điểm>[-nhãn]/, tự thử khôi phục
#   backup.sh list            liệt kê các bản sao lưu và kết quả kiểm tra
#   backup.sh restore <tên> --yes [--force]
#                             khôi phục database + storage từ bản <tên>. Phải dừng api/worker/beat trước;
#                             --force bỏ qua kiểm tra kết nối đang mở. Luôn sao lưu trạng thái hiện tại trước.
#
# Một bản sao lưu là một thư mục: db.dump (pg_dump -Fc), storage.tar.gz, SHA256SUMS, info.txt, STATUS (OK|WARN|FAILED).
# Thư mục chỉ xuất hiện dưới tên thật khi đã ghi xong (ghi vào .tmp-* rồi đổi tên) nên không có bản dở dang.
set -eu

BACKUP_ROOT=${BACKUP_ROOT:-/backups}
STORAGE_DIR=${STORAGE_DIR:-/data/storage}
BACKUP_AT=${BACKUP_AT:-19:30}
BACKUP_KEEP=${BACKUP_KEEP:-7}
export PGHOST="${PGHOST:-postgres}"
export PGUSER="${POSTGRES_USER:-dms}"
export PGPASSWORD="${POSTGRES_PASSWORD:?đặt POSTGRES_PASSWORD trong .env}"
export PGDATABASE="${POSTGRES_DB:-dms}"
export PGOPTIONS="-c client_min_messages=warning"   # bỏ NOTICE "does not exist, skipping"
VERIFY_DB="${PGDATABASE}_backup_verify"

log() { echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [backup] $*"; }
die() { log "LỖI: $*" >&2; exit 1; }
q() { psql -XAtq -v ON_ERROR_STOP=1 "$@"; }

# Số dòng các bảng chính, dạng "bảng=số" mỗi dòng (nội dung của bản sao lưu, ghi ra counts.txt).
counts() {
  local t
  for t in users categories documents document_pages ocr_results ocr_corrections processing_jobs audit_logs; do
    echo "$t=$(q -d "$1" -c "SELECT count(*) FROM $t")"
  done
}

prune() {
  # Giữ BACKUP_KEEP bản gần nhất có STATUS khác FAILED; bản FAILED cũ hơn bản tốt mới nhất cũng xóa.
  local kept=0 d status
  for d in $(ls -1d "$BACKUP_ROOT"/2* 2>/dev/null | sort -r); do
    status=$(cat "$d/STATUS" 2>/dev/null || echo FAILED)
    if [ "$status" != FAILED ] && [ "$kept" -lt "$BACKUP_KEEP" ]; then
      kept=$((kept + 1))
    elif [ "$kept" -gt 0 ]; then
      log "xóa bản cũ $(basename "$d")"
      rm -rf -- "$d"
    fi
  done
}

# Thử khôi phục bản dump vào database tạm và kiểm tra. In ra "OK" hoặc "WARN: ..."; lỗi nặng -> exit != 0.
verify() {
  local dir=$1 warn tables missing
  (cd "$dir" && sha256sum -c -s SHA256SUMS) || die "checksum không khớp"
  gzip -t "$dir/storage.tar.gz" || die "storage.tar.gz hỏng"
  q -d postgres -c "DROP DATABASE IF EXISTS \"$VERIFY_DB\"" -c "CREATE DATABASE \"$VERIFY_DB\""
  if ! pg_restore --exit-on-error --no-owner -d "$VERIFY_DB" "$dir/db.dump" 2>"$dir/verify.log"; then
    q -d postgres -c "DROP DATABASE IF EXISTS \"$VERIFY_DB\""
    die "pg_restore thất bại (xem verify.log)"
  fi
  warn=""
  # 1. Cùng revision Alembic và cùng số bảng với database đang chạy (schema khôi phục đầy đủ).
  [ "$(q -d "$VERIFY_DB" -c 'SELECT version_num FROM alembic_version')" = "$(sed -n 's/^alembic=//p' "$dir/info.txt")" ]     || warn="$warn alembic_version khác;"
  tables="SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'"
  [ "$(q -d "$VERIFY_DB" -c "$tables")" = "$(q -c "$tables")" ] || warn="$warn số bảng khác database đang chạy;"
  # 2. audit_logs chỉ ghi thêm (kể cả purge cũng giữ audit) -> bản sao lưu không thể nhiều dòng hơn hiện tại.
  [ "$(q -d "$VERIFY_DB" -c 'SELECT count(*) FROM audit_logs')" -le "$(q -c 'SELECT count(*) FROM audit_logs')" ]     || warn="$warn audit_logs nhiều hơn database đang chạy;"
  # 3. Mọi file database tham chiếu phải có trong storage.tar.gz. Thiếu chỉ xảy ra khi purge (FR-07) xóa file
  #    đúng lúc sao lưu (dump trước, nén file sau) -> cảnh báo, không coi là hỏng.
  q -d "$VERIFY_DB" -c "SELECT storage_key FROM documents UNION SELECT image_key FROM document_pages WHERE image_key <> ''"     | sort > "$dir/keys.db"
  tar -tzf "$dir/storage.tar.gz" | sed 's|^\./||' | grep -v '/$' | sort > "$dir/keys.tar" || true
  missing=$(comm -23 "$dir/keys.db" "$dir/keys.tar" | wc -l)
  [ "$missing" -eq 0 ] || warn="$warn $missing file được tham chiếu nhưng không có trong storage.tar.gz;"
  counts "$VERIFY_DB" > "$dir/counts.txt"
  rm -f "$dir/keys.db" "$dir/keys.tar"
  q -d postgres -c "DROP DATABASE \"$VERIFY_DB\""
  if [ -n "$warn" ]; then echo "WARN:$warn"; else echo OK; fi
}

# Biến trong hàm sh mặc định là toàn cục: mọi hàm khai báo "local" để run (gọi từ restore) không ghi đè
# biến của hàm gọi nó.
run() {
  local label=${1:-} name tmp dir result status
  name=$(date -u +%Y%m%d-%H%M%S)${label:+-$label}
  tmp="$BACKUP_ROOT/.tmp-$name"
  dir="$BACKUP_ROOT/$name"
  mkdir -p "$tmp"
  trap 'rm -rf -- "$tmp"' EXIT
  log "bắt đầu $name"
  # Database trước, file sau: file upload sau thời điểm dump chỉ là file thừa (vô hại); làm ngược lại thì
  # bản ghi mới trỏ tới file không có trong bản sao lưu.
  pg_dump -Fc -f "$tmp/db.dump"
  tar -C "$STORAGE_DIR" -czf "$tmp/storage.tar.gz" .
  (cd "$tmp" && sha256sum db.dump storage.tar.gz > SHA256SUMS)
  {
    echo "created_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "database=$PGDATABASE"
    echo "alembic=$(q -c 'SELECT version_num FROM alembic_version')"
    echo "db_bytes=$(wc -c < "$tmp/db.dump")"
    echo "storage_bytes=$(wc -c < "$tmp/storage.tar.gz")"
    echo "storage_files=$(tar -tzf "$tmp/storage.tar.gz" | grep -vc '/$' || true)"
  } > "$tmp/info.txt"
  mv "$tmp" "$dir"
  trap - EXIT
  if result=$(verify "$dir"); then
    echo "$result" > "$dir/STATUS.detail"
    status=${result%%:*}
  else
    status=FAILED
  fi
  echo "$status" > "$dir/STATUS"
  log "xong $name: $status $(sed 's/^OK$//; s/^WARN://' "$dir/STATUS.detail" 2>/dev/null)"
  # Khi đang khôi phục không dọn bản cũ: bản cần khôi phục có thể là bản cũ nhất.
  [ "${NO_PRUNE:-0}" = 1 ] || prune
  [ "$status" != FAILED ]
}

list() {
  local d
  printf '%-32s %-7s %12s %14s\n' "BẢN SAO LƯU" "KẾT QUẢ" "DB (byte)" "STORAGE (byte)"
  for d in $(ls -1d "$BACKUP_ROOT"/2* 2>/dev/null | sort -r); do
    printf '%-32s %-7s %12s %14s\n' "$(basename "$d")" "$(cat "$d/STATUS" 2>/dev/null || echo '?')" \
      "$(sed -n 's/^db_bytes=//p' "$d/info.txt")" "$(sed -n 's/^storage_bytes=//p' "$d/info.txt")"
  done
}

restore() {
  local name=${1:-} dir yes=0 force=0 a others owner
  shift || true
  for a in "$@"; do
    case $a in --yes) yes=1 ;; --force) force=1 ;; *) die "tham số lạ: $a" ;; esac
  done
  [ -n "$name" ] || die "cần tên bản sao lưu (xem: backup.sh list)"
  dir="$BACKUP_ROOT/$name"
  [ -f "$dir/db.dump" ] || die "không có bản $name"
  [ "$(cat "$dir/STATUS" 2>/dev/null)" != FAILED ] || die "bản $name có STATUS=FAILED, không khôi phục"
  [ "$yes" -eq 1 ] || die "khôi phục sẽ GHI ĐÈ database $PGDATABASE và storage; chạy lại với --yes"
  (cd "$dir" && sha256sum -c -s SHA256SUMS) || die "checksum không khớp, bản sao lưu đã bị sửa/hỏng"
  # Ứng dụng còn kết nối -> ghi đè giữa chừng sẽ hỏng dữ liệu. Dừng api, worker, beat trước (GUIDE 6.4).
  others=$(q -d postgres -c "SELECT count(*) FROM pg_stat_activity WHERE datname = '$PGDATABASE' AND pid <> pg_backend_pid()")
  if [ "$others" -gt 0 ] && [ "$force" -eq 0 ]; then
    die "còn $others kết nối tới $PGDATABASE: dừng api/worker/beat trước (docker compose stop api worker beat)"
  fi
  log "sao lưu trạng thái hiện tại trước khi ghi đè"
  NO_PRUNE=1 run pre-restore || die "không sao lưu được trạng thái hiện tại; dừng khôi phục"
  log "khôi phục database từ $name"
  q -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$PGDATABASE' AND pid <> pg_backend_pid()" >/dev/null
  q -d postgres -c "DROP DATABASE \"$PGDATABASE\"" -c "CREATE DATABASE \"$PGDATABASE\""
  pg_restore --exit-on-error --no-owner -d "$PGDATABASE" "$dir/db.dump"
  log "khôi phục storage từ $name"
  owner=$(stat -c '%u:%g' "$STORAGE_DIR")
  find "$STORAGE_DIR" -mindepth 1 -delete
  tar -C "$STORAGE_DIR" -xzf "$dir/storage.tar.gz"
  chown -R "$owner" "$STORAGE_DIR"   # giữ quyền của user app (uid 10001) để api/worker ghi tiếp được
  log "xong. Khởi động lại: docker compose up -d"
}

daemon() {
  local last now today
  log "lịch sao lưu hằng ngày lúc $BACKUP_AT (UTC), giữ $BACKUP_KEEP bản, thư mục $BACKUP_ROOT"
  last=""
  while :; do
    now=$(date -u +%H:%M) today=$(date -u +%Y-%m-%d)
    if [ "$now" = "$BACKUP_AT" ] && [ "$last" != "$today" ]; then
      last=$today
      run || log "sao lưu thất bại, thử lại vào lượt sau"
    fi
    sleep 20
  done
}

cmd=${1:-daemon}
[ $# -gt 0 ] && shift
case $cmd in
  daemon) daemon ;;
  run) run "$@" ;;
  list) list ;;
  restore) restore "$@" ;;
  *) die "lệnh không hỗ trợ: $cmd (daemon | run | list | restore)" ;;
esac
