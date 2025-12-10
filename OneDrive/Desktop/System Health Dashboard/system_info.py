import psutil
import mysql.connector
import time
conn = mysql.connector.connect(
    host="localhost",
    port=3306,
    user="root",
    password="admin321",  
    database="system_metrics"
)
cursor = conn.cursor()

def insert_metrics():

    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    net = psutil.net_io_counters()
    
    try:
        battery = psutil.sensors_battery()
        battery_percent = battery.percent
        battery_plugged = battery.power_plugged
    except:
        battery_percent = None
        battery_plugged = None


    memory_used_mb = mem.used / (1024 * 1024)
    disk_used_mb = disk.used / (1024 * 1024)
    bytes_sent_mb = net.bytes_sent / (1024 * 1024)
    bytes_recv_mb = net.bytes_recv / (1024 * 1024)

    
    query = """
        INSERT INTO metrics 
        (cpu_usage, memory_used, memory_percent, disk_used, disk_percent, bytes_sent, bytes_recv, battery_percent, battery_plugged) 
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    values = (cpu, memory_used_mb, mem.percent, disk_used_mb, disk.percent,
              bytes_sent_mb, bytes_recv_mb, battery_percent, battery_plugged)
    cursor.execute(query, values)
    conn.commit()

    
    cursor.execute("DELETE FROM metrics WHERE timestamp < NOW() - INTERVAL 5 MINUTE")
    conn.commit()

    print("✅ Live metrics updated at", time.strftime("%Y-%m-%d %H:%M:%S"))

while True:
    insert_metrics()
    time.sleep(5)
