import requests
from bs4 import BeautifulSoup
import re
import urllib3
from flask import Flask, make_response, jsonify, redirect, render_template
import mysql.connector
from flask_cors import CORS, cross_origin
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import os

conn = mysql.connector.connect(
  host=os.environ['DB_HOST'],
  port=os.environ['DB_PORT'],
  user=os.environ['DB_USERNAME'],
  password=os.environ['DB_PASSWORD'],
  database=os.environ['DB_DATABASE'],
  autocommit=True
)
cursor = conn.cursor()

cursor.execute('''
	CREATE TABLE IF NOT EXISTS departments (
		id INTEGER PRIMARY KEY AUTO_INCREMENT,
		server VARCHAR(255) NOT NULL,
		department VARCHAR(255) NOT NULL,
		acronym VARCHAR(255)
	)
''')
cursor.execute('''
	CREATE TABLE IF NOT EXISTS server_status (
		id INTEGER PRIMARY KEY AUTO_INCREMENT,
		server VARCHAR(255) NOT NULL,
		status BOOLEAN NOT NULL
	)
''')
cursor.execute('''
	CREATE TABLE IF NOT EXISTS last_updated (
		id INTEGER PRIMARY KEY AUTO_INCREMENT,
		updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
	)
''')

conn.commit()

servers = [
	"http://119.93.173.77:81/enroll/",
	"http://119.93.173.77:84/enroll/",
	"https://119.93.173.77/enroll/",
	"http://119.93.173.77:86/enroll/",
	"http://119.93.173.77:88/enroll/",
	"http://119.93.173.77:89/enroll/"
]

conversions = {
    "GS": {
        "value": "Graduate School",
        "acronym": "GS",
    },
    "CAS": {
        "value": "College of Arts and Sciences",
        "acronym": "CAS",
    },
    "LHS": {
        "value": "Laboratory High School",
        "acronym": "LHS",
    },
    "BSN": {
        "value": "College of Nursing",
        "acronym": "CON",
    },
    "BSAgri": {
        "value": "College of Agriculture",
        "acronym": "COAgri",
    },
    "CPTE": {
        "value": "Certificate in Professional Teacher Education",
        "acronym": "CPTE",
    },
    "CPE": {
        "value": "Certificate in Physical Education",
        "acronym": "CPE",
    },
    "CICT": {
        "value": "College of Information and Communications Technology",
        "acronym": "CICT",
    },
    "College of Education": {
        "value": "College of Education",
        "acronym": "COED",
    },
    "CMBT": {
        "value": "College of Management and Business Technology",
        "acronym": "CMBT",
    },
    "College of Engineering": {
        "value": "College of Engineering",
        "acronym": "COE",
    },
    "College of Criminology": {
        "value": "College of Criminology",
        "acronym": "COC",
    },
    "CoArchi": {
        "value": "College of Architecture",
        "acronym": "COArchi",
    },
    "CIT": {
        "value": "College of Industrial Technology",
        "acronym": "CIT",
    },
    "CPADM": {
        "value": "College of Public Administration and Disaster Management",
        "acronym": "CPADM",
    },
    "BALCS": {
        "value": "Institute of Linguistics and Literature",
        "acronym": "IOLL",
    },
}

def searchServers():
	conn = mysql.connector.connect(
		host=os.environ['DB_HOST'],
		port=os.environ['DB_PORT'],
		user=os.environ['DB_USERNAME'],
		password=os.environ['DB_PASSWORD'],
		database=os.environ['DB_DATABASE'],
		autocommit=True
	)
	conn.autocommit = True
	cursor = conn.cursor()

	for server in servers:
		try:
			r = requests.get(server, verify=False)
			r.raise_for_status()
			soup = BeautifulSoup(r.content, 'html.parser')
		except requests.exceptions.RequestException as e:
			cursor.execute('SELECT * FROM server_status WHERE server = %s', (server,))
			if cursor.fetchone() is None:
				cursor.execute('INSERT INTO server_status (server, status) VALUES (%s, %s)', (server, False))
			else:
				cursor.execute('UPDATE server_status SET status = %s WHERE server = %s', (False, server))
			continue

		server_label = (soup.select_one('#loginform > span:nth-child(3)')).text.strip().replace('&', ',')
		server_label = re.sub(r'\(Server \d+\)', '', server_label)
		

		if server_label.find(',') != -1:
			server_label = server_label.split(',')
			server_label = [x.strip() for x in server_label if x.strip()]
		else:
			server_label = [server_label.strip()]

		newDeptData = []
		for dept in server_label:
			dept_name = conversions.get(dept)['value'] or dept
			cursor.execute('SELECT * FROM departments WHERE server = %s AND department = %s', (server, dept_name))

			if cursor.fetchone() is None:
				dept_data = conversions.get(dept, None)
				if dept_data is not None:
					if 'value' in dept_data and 'acronym' in dept_data:
						cursor.execute('INSERT INTO departments (server, department, acronym) VALUES (%s, %s, %s)', (server, dept_data['value'], dept_data['acronym']))
						newDeptData.append((server, dept_data['value'], dept_data['acronym']))
					else:
						cursor.execute('INSERT INTO departments (server, department, acronym) VALUES (%s, %s, %s)', (server, dept_name, None))
						newDeptData.append((server, dept_name, None))
				else:
					cursor.execute('INSERT INTO departments (server, department, acronym) VALUES (%s, %s, %s)', (server, dept_name, None))
					newDeptData.append((server, dept_name, None))
		

		cursor.execute('SELECT department FROM departments WHERE server = %s', (server,))
		existing_departments = cursor.fetchall()
		existing_departments = [dept[0] for dept in existing_departments]

		for existing_dept in existing_departments:
			converted_dept = next((key for key, value in conversions.items() if value['value'] == existing_dept), None)
			if converted_dept is None:
				cursor.execute('DELETE FROM departments WHERE server = %s AND department = %s', (server, existing_dept))
				continue
			if converted_dept not in server_label:
				cursor.execute('DELETE FROM departments WHERE server = %s AND department = %s', (server, existing_dept))			

		cursor.execute('SELECT * FROM server_status WHERE server = %s', (server,))
		if cursor.fetchone() is None:
			cursor.execute('INSERT INTO server_status (server, status) VALUES (%s, %s)', (server, True))
		conn.commit()
	
	cursor.execute('INSERT INTO last_updated (updated_at) VALUES (CURRENT_TIMESTAMP)')
	conn.commit()


def checkTables():
	conn = mysql.connector.connect(
		host=os.environ['DB_HOST'],
		port=os.environ['DB_PORT'],
		user=os.environ['DB_USERNAME'],
		password=os.environ['DB_PASSWORD'],
		database=os.environ['DB_DATABASE']
	)
	cursor = conn.cursor()

	cursor.execute('SELECT COUNT(*) FROM departments')
	departments_count = cursor.fetchone()[0]
	cursor.execute('SELECT COUNT(*) FROM server_status')
	server_status_count = cursor.fetchone()[0]
	if departments_count == 0 or server_status_count == 0:
		searchServers()
	cursor.close()
	conn.close()

checkTables()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
app = Flask(__name__, subdomain_matching=True)
app.config['SERVER_NAME'] = os.environ['BASE_URL']
CORS(app)

scheduler = BackgroundScheduler()
scheduler.add_job(func=searchServers, trigger="interval", seconds=3600)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

@app.route("/", subdomain="api")
@cross_origin()
def apiIndex():
	cursor = conn.cursor()
	cursor.execute('SELECT server, department, acronym FROM departments')
	departments = cursor.fetchall()

	cursor.execute('SELECT server, status FROM server_status')
	server_status = cursor.fetchall()

	cursor.execute('SELECT UNIX_TIMESTAMP(updated_at) FROM last_updated ORDER BY id DESC LIMIT 1')
	last_updated = cursor.fetchone()

	data = {
		"departments": [
			{"server": row[0], "department": row[1], "acronym": row[2]}
			for row in departments
		],
		"server_status": [
			{"server": row[0], "status": bool(row[1])}
			for row in server_status
		],
		"last_updated": last_updated[0]
	}
	cursor.close()
	return data

@app.route("/", subdomain="<dept>")
@cross_origin()
def deptIndex(dept):
	if dept.lower().startswith('server-'):
		serverIndex = int(dept.split('-')[1])
		if serverIndex <= 0 or serverIndex > len(servers):
			return make_response(jsonify({
				"error": f"Server index '{serverIndex}' not found"
			}), 404)
		return redirect(servers[serverIndex - 1], 308)		

	cursor = conn.cursor()
	cursor.execute('SELECT server FROM departments WHERE acronym = %s', (dept,))
	serverLink = cursor.fetchone()

	cursor.close()
	if not serverLink:
		return make_response(jsonify({
			"error": f"Subdomain '{dept}' not found"
		}), 404)

	return render_template('redirect.html', dept=dept.upper(), server=serverLink[0])	