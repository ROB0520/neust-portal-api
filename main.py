from datetime import datetime
import requests
from bs4 import BeautifulSoup
import re
import urllib3
from flask import Flask, render_template
import mysql.connector
from flask_cors import CORS, cross_origin
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import os
from dotenv import load_dotenv

load_dotenv()

conn = mysql.connector.connect(
	host=os.environ.get('DB_HOST', 'localhost'),
	port=os.environ.get('DB_PORT', 3306),
	user=os.environ.get('DB_USERNAME', 'root'),
	password=os.environ.get('DB_PASSWORD', ''),
	database=os.environ.get('DB_DATABASE', 'neust_portal_api'),
	autocommit=True
)
cursor = conn.cursor()

cursor.execute('''
	CREATE TABLE IF NOT EXISTS colleges (
		id        INT     PRIMARY KEY AUTO_INCREMENT,
		name      VARCHAR(255) NOT NULL,
		acronym   VARCHAR(255) NULL    ,
		subdomain VARCHAR(255) NOT NULL,
		original  VARCHAR(255) NULL    ,
		server_id INT     NULL
	);
''')

cursor.execute('''
	CREATE TABLE IF NOT EXISTS servers (
		id        INT     PRIMARY KEY AUTO_INCREMENT,
		name      VARCHAR(255) NOT NULL,
		link      VARCHAR(255) NOT NULL,
		subdomain VARCHAR(255) NULL    ,
		status    BOOLEAN NULL     DEFAULT false
	);
''')

cursor.execute('SELECT COUNT(*) FROM servers')
servers_count = cursor.fetchone()[0]
if servers_count == 0:
    cursor.execute('''
        INSERT INTO servers (name, link, subdomain, status)
        VALUES 
        ('Server 1', 'http://119.93.173.77:81/enroll/', 'server-1', FALSE),
        ('Server 2', 'http://119.93.173.77:84/enroll/', 'server-2', FALSE),
        ('Server 3', 'https://119.93.173.77/enroll/', 'server-3', FALSE),
        ('Server 4', 'http://119.93.173.77:86/enroll/', 'server-4', FALSE),
        ('Server 5', 'http://119.93.173.77:88/enroll/', 'server-5', FALSE),
        ('Server 6', 'http://119.93.173.77:89/enroll/', 'server-6', FALSE)
    ''')

cursor.execute('SELECT COUNT(*) FROM colleges')
colleges_count = cursor.fetchone()[0]
if colleges_count == 0:
	cursor.execute('''
		INSERT INTO colleges (name, acronym, subdomain, original, server_id)
		VALUES 
		('Graduate School', 'GS', 'gs', 'GS', 1),
		('College of Arts and Sciences', 'CAS', 'cas', 'CAS', 1),
		('Laboratory High School', 'LHS', 'lhs', 'LHS', 1),
		('College of Nursing', 'CON', 'con', 'BSN', 1),
		('College of Agriculture', 'COAgri', 'coagri', 'BSAgri', 1),
		('Certificate in Professional Teacher Education', 'CPTE', 'cpte', 'CPTE', 1),
		('Certificate in Physical Education', 'CPE', 'cpe', 'CPE', 1),
		('College of Information and Communications Technology', 'CICT', 'cict', 'CICT', 2),
		('College of Education', 'COED', 'coed', 'College of Education', 3),
		('College of Management and Business Technology', 'CMBT', 'cmbt', 'CMBT', 4),
		('College of Engineering', 'COE', 'coe', 'College of Engineering', 5),
		('College of Criminology', 'COC', 'coc', 'College of Criminology', 5),
		('College of Architecture', 'COArchi', 'coarchi', 'CoArchi', 6),
		('College of Industrial Technology', 'CIT', 'cit', 'CIT', 6),
		('College of Public Administration and Disaster Management', 'CPADM', 'cpadm', 'CPADM', 6),
		('Institute of Linguistics and Literature', 'IOLL', 'ioll', 'BALCS', 6)
	''')

cursor.execute('''
	CREATE TABLE IF NOT EXISTS last_updated (
		id           INT       PRIMARY KEY AUTO_INCREMENT,
		updated_at 	 TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
	);
''')

def searchServers():
	cursor = conn.cursor()

	cursor.execute('SELECT link FROM servers')
	servers = [row[0] for row in cursor.fetchall()]

	for server in servers:
		try:
			r = requests.get(server, verify=False)
			r.raise_for_status()
			soup = BeautifulSoup(r.content, 'html.parser')
		except requests.exceptions.RequestException as e:
			cursor.execute('UPDATE servers SET status = %s WHERE link = %s', (False, server))
			conn.commit()
			continue

		server_label = (soup.select_one('#loginform > span:nth-child(3)')).text.strip().replace('&', ',')
		server_name, server_colleges = server_label.split(')', 1)
		server_name = server_name.strip().replace('(', '')
		server_colleges = server_colleges.strip().replace('&', ',')
		
		if server_colleges.find(',') != -1:
			server_colleges = server_colleges.split(',')
			server_colleges = [x.strip() for x in server_colleges if x.strip()]
		else:
			server_colleges = [server_colleges.strip()]
		
		cursor.execute('SELECT original, name, acronym FROM colleges WHERE server_id = (SELECT id FROM servers WHERE link = %s)', (server,))
		existing_colleges = cursor.fetchall()

		for college in server_colleges:
			if college not in [x[0] for x in existing_colleges]:
				cursor.execute('INSERT INTO colleges (name, acronym, subdomain, original, server_id) VALUES (%s, %s, %s, %s, (SELECT id FROM servers WHERE link = %s))', (college, '', college.lower(), college, server))

		for existing_college in existing_colleges:
			if existing_college[0] not in server_colleges:
				cursor.execute('SELECT server_id FROM colleges WHERE original = %s', (existing_college[0],))
				other_server_id = cursor.fetchone()
				if other_server_id is None:
					cursor.execute('UPDATE colleges SET server_id = (SELECT id FROM servers WHERE link = %s) WHERE original = %s', (server, existing_college[0]))
				else:
					cursor.execute('UPDATE colleges SET server_id = %s WHERE original = %s', (other_server_id, existing_college[0]))
			
		cursor.execute('UPDATE servers SET status = %s WHERE link = %s', (True, server))
		conn.commit()
	
	cursor.execute('DELETE FROM last_updated')
	cursor.execute('INSERT INTO last_updated (updated_at) VALUES (CURRENT_TIMESTAMP)')
	conn.commit()

cursor.execute('SELECT updated_at FROM last_updated ORDER BY id DESC LIMIT 1')
last_updated = cursor.fetchone()
if last_updated is None or (datetime.now() - last_updated[0]).days > 1:
	searchServers()

cursor.close()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
app = Flask(__name__, subdomain_matching=True)
app.config['SERVER_NAME'] = os.environ['BASE_URL']
CORS(app)

scheduler = BackgroundScheduler()
scheduler.add_job(func=searchServers, trigger="interval", seconds=3600)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

@app.route("/", subdomain="<subdomain>")
@cross_origin()
def apiIndex(subdomain):
	if subdomain.startswith('www.'):
		subdomain = subdomain[4:]

	cursor = conn.cursor()
	match subdomain:
		case 'api':
			cursor.execute('SELECT name, acronym, subdomain, server_id FROM colleges')
			colleges = cursor.fetchall()

			cursor.execute('SELECT name, link, status, id FROM servers')
			servers = cursor.fetchall()

			cursor.execute('SELECT UNIX_TIMESTAMP(updated_at) FROM last_updated ORDER BY id DESC LIMIT 1')
			last_updated = cursor.fetchone()

			data = {
				"colleges": [
					{"name": row[0], "acronym": row[1], "subdomain": row[2], "server_id": row[3]}
					for row in colleges if row[3] is not None
				],
				"servers": [
					{"name": row[0], "link": row[1], "status": bool(row[2]), "id": row[3]}
					for row in servers
				],
				"last_updated": last_updated[0] if last_updated else None
			}
			cursor.close()
			return data
		case _:
			cursor.execute('SELECT subdomain FROM servers WHERE subdomain IS NOT NULL')
			server_subdomains = cursor.fetchall()
			server_subdomains = [row[0] for row in server_subdomains]
			if subdomain in server_subdomains:
				cursor.execute('SELECT link, name FROM servers WHERE subdomain = %s', (subdomain,))
				[ server_link, name ] = cursor.fetchone()
				cursor.close()
				return render_template('redirect.html', dept=name, url=server_link)
			else:
				cursor.execute('SELECT link FROM servers WHERE id = (SELECT server_id FROM colleges WHERE subdomain = %s)', (subdomain,))
				college_link = cursor.fetchone()
				cursor.close()
				if not college_link:
					return render_template('no-redirect.html', dept=subdomain.upper(), url=f'https://{os.environ["BASE_URL"]}')
				return render_template('redirect.html', dept=subdomain.upper(), url=college_link[0])