#!/usr/bin/env python3
import base64
import requests
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
import http.client
import json
import time
import datetime
from urllib.parse import urlencode, quote_plus
from threading import Thread as thread
from investment_handler import Investment_Handler
from quant_view import Quant_View
import feed_handler as feed_handler
from logger import Logger
import traceback

#Load config (has information about login, path to api, and certificate file location)
with open('lib/config.json') as json_data_file:
    config = json.load(json_data_file)

USERNAME = config['login']['username']
PASSWORD = config['login']['password']
SERVICE = config['api-info']['service']
ACCOUNT_NUMBER = config['login']['accountnumber'] #might differ between live and test environment
URL = config['api-info']['url']
API_VERSION = config['api-info']['api_version']
headers = config['api-info']['headers']

#Only doing logging certain days
SATURDAY = config['hours']['saturday'] #5
SUNDAY = config['hours']['sunday'] #6


#Program tracking variable
global_number_of_fails = 0

#get_hash: Generate authhash
def get_hash(username, password):
	timestamp = int(round(time.time() * 1000))
	timestamp = str(timestamp).encode('ascii')
	
	username_b64 = base64.b64encode(username.encode('ascii'))
	password_b64 = base64.b64encode(password.encode('ascii'))
	timestamp_b64 = base64.b64encode(timestamp)
	
	auth_val = username_b64 + b':' + password_b64 + b':' + timestamp_b64
	rsa_key = RSA.importKey(open(config['login']['certificate']).read())
	cipher_rsa = PKCS1_v1_5.new(rsa_key)
	encrypted_hash = cipher_rsa.encrypt(auth_val)
	encoded_hash = base64.b64encode(encrypted_hash)
	
	return encoded_hash

		
#main: Start of the program
def main():
	
	#Variable to check how many times we've been thrown out
	global global_number_of_fails
	global_number_of_fails +=1
	
	#generate auth_hash
	auth_hash = get_hash(USERNAME, PASSWORD)
    
    #Start feeds etc.
	initiate_program(auth_hash)


#initiate_program: Using the login information, initiate feeds and investment class
def initiate_program(auth_hash):
	
    #Variable to check history writing
    history_writer_tracker = {'current_minute': datetime.datetime.now().minute}
    loggervariable = Logger(config)
    
	#Setup shared status information
    global shared_status_variable
    stop_loss_variable = {'no_big_loss': True, 'last_order': datetime.datetime(2000,1,1,1,1,1,1), 'initial_total_portfolio_value': 0, 'total_portfolio_value_morning': 0} #Used to stop trading if value falls below certain level and to stop high-frequency fails
    shared_status_variable = {'rpuf': True, 'rprf': True, 'rivh': True, 'exception': "none", 'available_funds': 0.0, 'have_positions': False, 'current_orders': False, 'stop_loss': stop_loss_variable}
	
	#Setup asset tracking variable (identifier + market id = UID)
    global shared_asset_variable
    shared_asset_variable = {}
		
	
    try:
		#Login-call
        payload = {'service': SERVICE, 'auth': auth_hash}
        r = requests.post('https://' + URL + '/next/'+ API_VERSION + '/login', data=payload, headers=headers)
        j = json.loads(r.text)
        
		#Setup variables for feeds and other api-calls 
        session_key = j['session_key']
        private_feed_hostname = j['private_feed']['hostname']
        private_feed_port = j['private_feed']['port']
        public_feed_hostname = j['public_feed']['hostname']
        public_feed_port = j['public_feed']['port']	
		
		#Setup quantview 
        quant_view = Quant_View()
        quant_view.initialize(shared_asset_variable, loggervariable)
		
		#Setup investment handler class
        r = requests.get('https://' + URL + '/next/'+ API_VERSION + '/accounts', auth=(session_key, session_key), headers=headers)
        j = json.loads(r.text)
        account_number = j[ACCOUNT_NUMBER]['accno']
        investment_handler = Investment_Handler(session_key, account_number, quant_view, shared_status_variable, shared_asset_variable, loggervariable, config)
        
		#Setup thread variables	
        private_feed_thread = thread(target = feed_handler.start_private_feed, args=[session_key, private_feed_hostname, private_feed_port, investment_handler, shared_status_variable, shared_asset_variable])
        public_feed_thread = thread(target = feed_handler.start_public_feed, args=[session_key, public_feed_hostname, public_feed_port, investment_handler, quant_view, shared_status_variable, shared_asset_variable])
        investment_handler_thread = thread(target = investment_handler.start_trading, args=[shared_status_variable, shared_asset_variable])
		
        private_feed_thread.start()
        public_feed_thread.start()
        investment_handler_thread.start()
		
		#While the run-feed variables are true the the threads will be alive. When false they will close
        while private_feed_thread.isAlive() or public_feed_thread.isAlive() or investment_handler_thread.isAlive():
			
            current_time = datetime.datetime.now()
			
			#For logging history purposes
            if (current_time.strftime("%H:%M")>=investment_handler.START_LOGGING and current_time.strftime("%H:%M")<=investment_handler.STOP_LOGGING and (current_time.weekday()!=SATURDAY and current_time.weekday()!=SUNDAY)):
                if history_writer_tracker['current_minute'] != current_time.minute:
                    history_writer_tracker = {'current_minute': current_time.minute}
                    loggervariable.write_history(shared_asset_variable)
					
					#Based on new historic data, we can update trade indicators
                    quant_view.update_indicators(investment_handler, shared_status_variable, shared_asset_variable, current_time)
												
			#If one of the threads, we discontinue the loop
            if not private_feed_thread.isAlive() or not public_feed_thread.isAlive() or not investment_handler_thread.isAlive():
                shared_status_variable['rpuf'] = False
                shared_status_variable['rprf'] = False
                shared_status_variable['rivh'] = False
		
		#Raise the exception so that we can log it
        raise Exception(shared_status_variable['exception'])
	
    except Exception as e:
		
		#Make sure to kill all threads before restarting. First checking if declared
        if 'private_feed_thread' in locals():
            while private_feed_thread.isAlive() or public_feed_thread.isAlive() or investment_handler_thread.isAlive():
                shared_status_variable['rpuf'] = False
                shared_status_variable['rprf'] = False
                shared_status_variable['rivh'] = False
		
		#If the exception is 'none' the main program must have crashed, get error!		
        if shared_status_variable['exception']=='none':
            shared_status_variable['exception']=str(traceback.format_exc())
		
		#When feeds are off, we logout from api
        r = requests.delete('https://' + URL + '/next/'+ API_VERSION + '/login', auth=(session_key, session_key), headers=headers)
		
		#Depending on how many times we've been thrown out, sleep, then reconnect
        if global_number_of_fails==2:
            print('Sleeping 5 second')
            time.sleep(5)
        elif global_number_of_fails>=3:
            print('Sleeping 30 second')
            time.sleep(30)
		
		#Log what has happened
        loggervariable.write_log("Number of fails: " + str(global_number_of_fails) + " Error message: " + str(shared_status_variable['exception']))
        shared_status_variable['exception'] = 'none'	
		
		#Reconnect/rerun program
        main()


if __name__ == "__main__":
	main()