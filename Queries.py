import pyodbc

def GetUsers():
    users = []
    try:
        conn = pyodbc.connect("Driver={ODBC Driver 18 for SQL Server};"
                              "Server=tcp:swan-river-user-information.database.windows.net,1433;"
                              "Database=UserDatabase;"
                              "Uid=jcwill23@cougarnet.uh.edu@swan-river-user-information;"
                              "Pwd=H1ghLander;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;")
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, role, status FROM Users")  # Adjust columns based on your table
        users = cursor.fetchall()
        cursor.close()
        conn.close()
    except pyodbc.Error as e:
        print("Database error:", e)
    return users

