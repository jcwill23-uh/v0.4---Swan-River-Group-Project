import simplejson as json
import pyodbc as db

def AddUser(string):
  data = [v for k, v in json.loads(string).items()]
  e = None
  with db.connect("Driver={ODBC Driver 18 for SQL Server};Server=tcp:swan-river.database.windows.net,1433;Database=SRDB;Uid=TRD159;Pwd={your_password_here};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;") as conn:
    with conn.cursor() as cursor:
      try:
        cursor.execute("INSERT INTO Users VALUES (?, ?, ?, ?)", (data[0], data[1], data[2], data[3]))
      except pyodbc.DatabaseError as error:
        e = error
      finally:
        cursor.close()
    conn.close()
  if (not e is None):
    return e
