{
  echo "source base"
  echo "{"
  echo "  type = pgsql"
  echo "  sql_host = $DB_HOST"
  echo "  sql_user = $DB_USERNAME"
  echo "  sql_pass = $DB_PASSWORD"
  echo "  sql_db = $DB_NAME"
  echo "}"
  cat /app/sphinx/sphinx.conf
} > /app/sphinx/sphinx.conf.new

mv /app/sphinx/sphinx.conf.new /app/sphinx/sphinx.conf

indexer --all --config /app/sphinx/sphinx.conf

searchd --nodetach --config /app/sphinx/sphinx.conf
