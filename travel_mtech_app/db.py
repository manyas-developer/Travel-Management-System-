import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root@1823",       # your MySQL password
        database="travel_mtech_final"
    )
