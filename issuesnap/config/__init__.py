# PyMySQL as MySQLdb fallback — required when mysqlclient is not compiled
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass
