import json
import sys

import socket, ssl, pprint
import http.client
from time import sleep
from threading import Thread as thread
import datetime
import requests
import pprint
import math
import traceback
import logger as logger
import quant_view as quant_view
import pandas as pd
import pprint


class Investment_Handler:
	
	#Variable to print better
    pp = pprint.PrettyPrinter(indent=4)
    
	#init: Constructor of class. Will set the key variables to perform trading
    def __init__(self, session_key, account_number, quant_view, shared_status_variable, shared_asset_variable, loggervariable, config):
        self.session_key = session_key
        self.account_number = account_number
        self.quant_view = quant_view
        self.SERVICE = config['api-info']['service']
        self.URL = config['api-info']['url']
        self.API_VERSION = config['api-info']['api_version']
        self.HEADERS = config['api-info']['headers']
		
		#Hours of trading
        self.RESET_LOSS_SAFETY = config['hours']['reset_loss_safety']
        self.CANCEL_MORNING_ORDERS = config['hours']['cancel_morning_orders']
        self.TRADE_HOURS_OPEN = config['hours']['trade_hours_open']
        self.TRADE_HOURS_CLOSE = config['hours']['trade_hours_close']
        self.CANCEL_EVENING_ORDERS = config['hours']['cancel_evening_orders']
        self.SATURDAY = config['hours']['saturday'] #5
        self.SUNDAY = config['hours']['sunday'] #6
		
		#Hours of logging
        self.START_LOGGING = config['hours']['start_logging']
        self.STOP_LOGGING = config['hours']['stop_logging']
        
        #check current status of orders and holdings
        self.check_current_status(shared_status_variable, shared_asset_variable)
		
		#Set Variable for logging purposes
        self.loggervariable = loggervariable
        
	#check_current_status: Run at initialization	
    def check_current_status(self,shared_status_variable, shared_asset_variable):
		
        payload = {}

        #Check pending orders		
        r = requests.get('https://' + self.URL + '/next/'+ self.API_VERSION + '/accounts/' + str(self.account_number) + '/orders', auth=(self.session_key, self.session_key), data=payload, headers=self.HEADERS)
        if(r.status_code==204):
            shared_status_variable['current_orders'] = False
        else:
            j = json.loads(r.text)
            pending_orders = [x for x in j if ( ('action_state' in x and x['action_state'] == 'INS_PEND') or ('order_state' in x and x['order_state'] == 'ON_MARKET') )]
						
            if(len(pending_orders)>0):
                shared_status_variable['current_orders'] = True

		#Check if we have positions
        r = requests.get('https://' + self.URL + '/next/'+ self.API_VERSION + '/accounts/' + str(self.account_number) + '/positions', auth=(self.session_key, self.session_key), data=payload, headers=self.HEADERS)	
        if(r.status_code==204):
            shared_status_variable['have_positions'] = False
        else:
            j = json.loads(r.text)
            
			#Check if we have traded the asset (checking isin_code)
            for key in shared_asset_variable:
                positions_in_asset = [x for x in j if x['instrument']['isin_code'] == shared_asset_variable[key]['isin']]
                if(len(positions_in_asset)>0):
                    shared_status_variable['have_positions'] = True
                    shared_asset_variable[key]['position_acq_price'] = positions_in_asset[0]['acq_price_acc']['value']
                    shared_asset_variable[key]['position_qty'] = positions_in_asset[0]['qty']
				
		#Finally, check cash and initial portfolio value (for stop loss)
        r = requests.get('https://' + self.URL + '/next/'+ self.API_VERSION + '/accounts/' + str(self.account_number), auth=(self.session_key, self.session_key), data=payload, headers=self.HEADERS)
        j = json.loads(r.text)
        shared_status_variable['available_funds'] = j['trading_power']['value']
        shared_status_variable['stop_loss']['initial_total_portfolio_value'] = j['own_capital']['value']
        shared_status_variable['stop_loss']['total_portfolio_value_morning'] = j['own_capital_morning']['value']
	
	
	#check_if_we_have_positions: Checking if we have positions (used to check whenever there is a sale)
    def check_if_we_have_positions(self, shared_status_variable, shared_asset_variable):
		
		#Boolean used in the checking of all the assets
        have_pos = False
		
		#Loop through all the assets to check if we have positions
        for key in shared_asset_variable:
            if shared_asset_variable[key]['position_qty']>0:
                have_pos = True
                continue
		
		#Finally, set status
        shared_status_variable['have_positions'] = have_pos 
	
	
	#buy: Buy function, will be triggered from quant view depending on strategy	
    def buy(self, shared_status_variable, shared_asset_variable, key, price, asked_volume, MAXIMUM_TRADE_VOLUME):
		
		#Setting orders to true. Will be set to false in the private feed when it is done
        shared_status_variable['current_orders'] = True
		
		#Check cash, api call...
        payload = {}
        r = requests.get('https://' + self.URL + '/next/'+ self.API_VERSION + '/accounts/' + str(self.account_number), auth=(self.session_key, self.session_key), data=payload, headers=self.HEADERS)
        j = json.loads(r.text)
        current_cash = 0
        if 'trading_power' in j:
            current_cash = shared_status_variable['available_funds'] = j['trading_power']['value']
        else:
            shared_status_variable['current_orders'] = False
            return #If no cash, no trade...
		
		#What can we buy? Check the minimum of the upper limits (depending on cash, bidded volume, and upper buy limits)
        upper_limit_volume = MAXIMUM_TRADE_VOLUME/price
        qty_can_be_bought = current_cash/price
        amount_to_buy = math.floor(min(qty_can_be_bought, upper_limit_volume, asked_volume))
		
		#Calling the api to buy the asset
        payload = {'identifier': shared_asset_variable[key]['identifier'], 'market_id': shared_asset_variable[key]['market_id'], 'currency': 'SEK', 'price': price, 'volume': amount_to_buy, 'side': 'BUY', 'order_type': 'FOK'}
        r = requests.post('https://' + self.URL + '/next/'+ self.API_VERSION + '/accounts/' + str(self.account_number) + '/orders', auth=(self.session_key, self.session_key), data=payload, headers=self.HEADERS)
        j = json.loads(r.text)
		
		#If something and deleted went wrong we need to correct.
        if 'order_state' in j and j['order_state'] == 'DELETED':
            shared_status_variable['current_orders'] = False
		
		#Set last order_variable to prevent HFT-losses
        shared_status_variable['stop_loss']['last_order'] = datetime.datetime.now()
			
		#Log the information
        self.loggervariable.write_log("Buying: " + str(j) + " Payload: " + str(payload))	
			
	
	#sell: Will be used when it is time to sell (end of day or when trading strategy indicates)	
    def sell(self, shared_status_variable, shared_asset_variable, key, price):
        
		#Setting orders to true. Will be set to false in the private feed when it is done
        shared_status_variable['current_orders'] = True

		#Calling the api to sell the asset
        payload = {'identifier': shared_asset_variable[key]['identifier'], 'market_id': shared_asset_variable[key]['market_id'], 'currency': 'SEK', 'price': price, 'volume': shared_asset_variable[key]['position_qty'], 'side': 'SELL', 'order_type': 'FOK'}			
        r = requests.post('https://' + self.URL + '/next/'+ self.API_VERSION + '/accounts/' + str(self.account_number) + '/orders', auth=(self.session_key, self.session_key), data=payload, headers=self.HEADERS)
        j = json.loads(r.text)

		#If something and deleted went wrong we need to correct.
        if 'order_state' in j and j['order_state'] == 'DELETED':
            shared_status_variable['current_orders'] = False

		#Set last order_variable to prevent HFT-losses
        shared_status_variable['stop_loss']['last_order'] = datetime.datetime.now()

		#Log the information
        j = json.loads(r.text)
        self.loggervariable.write_log("Selling: " + str(j) + " Payload: " + str(payload))
				
	
	#end_of_day_sell: Will be used to try to sell remaining positions we have in the instruments.	
    def end_of_day_sell(self, shared_status_variable, shared_asset_variable, key, why):
        
		#Setting orders to true. Will be set to false in the private feed when it is done
        shared_status_variable['current_orders'] = True
		
		#We don't want to keep trading if end of day sell is triggered.
        shared_status_variable['stop_loss']['no_big_loss'] = False
        
		#Calling the api to sell the asset
        payload = {'identifier': shared_asset_variable[key]['identifier'], 'market_id': shared_asset_variable[key]['market_id'], 'currency': 'SEK', 'price': shared_asset_variable[key]['current_bid'], 'volume': shared_asset_variable[key]['position_qty'], 'side': 'SELL'}			
        r = requests.post('https://' + self.URL + '/next/'+ self.API_VERSION + '/accounts/' + str(self.account_number) + '/orders', auth=(self.session_key, self.session_key), data=payload, headers=self.HEADERS)
        j = json.loads(r.text)
        
		#If something and deleted went wrong we need to correct.
        if 'order_state' in j and j['order_state'] == 'DELETED':
            shared_status_variable['current_orders'] = False
            
		#Set last order_variable to prevent HFT-losses
        shared_status_variable['stop_loss']['last_order'] = datetime.datetime.now()
        
		#Log the information
        j = json.loads(r.text)
        self.loggervariable.write_important_message("End of day selling: " + str(j) + " Payload: " + str(payload) + "\n Why: " + why)
        
        
	#cancel_orders: Will be used in the end of the day to cancel pending orders...		
    def cancel_orders(self, shared_status_variable):
        
		#Get all the orders
        payload = {}
        r = requests.get('https://' + self.URL + '/next/'+ self.API_VERSION + '/accounts/' + str(self.account_number) + '/orders', auth=(self.session_key, self.session_key), data=payload, headers=self.HEADERS)
		
		#Check if empty
        if(r.status_code==204):
            self.loggervariable.write_log("No orders to cancel: " + str(r.status_code))
        else:
            j = json.loads(r.text)
			
			#Sort the ones that are "pending..."
            pending_orders = [x for x in j if ( ('action_state' in x and x['action_state'] == 'INS_PEND') or ('order_state' in x and x['order_state'] == 'ON_MARKET') )]
            
			#For all of the pending orders, try to cancel. Log information.
            for i in range(len(pending_orders)):
                r = requests.delete('https://' + self.URL + '/next/'+ self.API_VERSION + '/accounts/' + str(self.account_number) + '/orders/' + str(pending_orders[i]['order_id']), auth=(self.session_key, self.session_key), data=payload, headers=self.HEADERS)
                j = json.loads(r.text)
                self.loggervariable.write_log("Cancelling orders: " + str(j))
                
	
	#check_if_logged_in: Housekeeping function called from schedule in quant_view
    def check_if_logged_in(self, shared_status_variable):
        r = requests.put('https://' + self.URL + '/next/'+ self.API_VERSION + '/login', auth=(self.session_key, self.session_key), headers=self.HEADERS)
        j = json.loads(r.text)
        if not ('logged_in' in j and j['logged_in'] == True) or ('code' in j and j['code'] == 'NEXT_INVALID_SESSION'):
            shared_status_variable['exception'] = "We got logged out for some reason"
            shared_status_variable['rivh'] = False
            

	#check_stop_loss: Housekeeping function called from schedule in quant_view
    def check_stop_loss(self, shared_status_variable):
        
        payload = {}
        r = requests.get('https://' + self.URL + '/next/'+ self.API_VERSION + '/accounts/' + str(self.account_number), auth=(self.session_key, self.session_key), data=payload, headers=self.HEADERS)
        j = json.loads(r.text)
        current_portfolio_value = j['own_capital']['value']
        
        if current_portfolio_value<0.95*shared_status_variable['stop_loss']['initial_total_portfolio_value'] or current_portfolio_value<shared_status_variable['stop_loss']['total_portfolio_value_morning']*0.95:
            shared_status_variable['stop_loss']['no_big_loss'] = False
            
			#Trigger end of day sell function... 
            for key in shared_asset_variable:
                why = "We've lost too much money :("
                self.end_of_day_sell(shared_status_variable, shared_asset_variable, key, why)

	
	#ok_to_trade: Returns a boolean to check if it is ok to trade
    def ok_to_trade(self, shared_status_variable, side, shared_asset_variable, key):
        
        current_datetime = datetime.datetime.now()
        current_time = current_datetime.strftime("%H:%M")
        
		#Only trade during specified trade hours
        if self.TRADE_HOURS_OPEN<current_time and current_time<self.TRADE_HOURS_CLOSE and (current_datetime.weekday()!=self.SATURDAY and current_datetime.weekday()!=self.SUNDAY):
            
			#We don't want to trade if we lost to much value or if we recently tried to trade but failed.
            if shared_status_variable['stop_loss']['no_big_loss'] == False or shared_status_variable['stop_loss']['last_order']>current_datetime-datetime.timedelta(minutes=2):
                return False
				
			#We don't want to trade if we have current orders or the indicator has not been updated in a while.
            elif shared_status_variable['current_orders'] == True or shared_asset_variable[key]['indicator']['updated_at']<current_datetime-datetime.timedelta(minutes=1):
                return False
			
			#Depending on the side we need to check if we can trade
            elif (side == "BUY" and shared_status_variable['have_positions']) or (side == "SELL" and not shared_status_variable['have_positions']):
                return False
			
			#Otherwise trade :)
            else:
                return True
            
        else:
            return False
		
	
	#start_trading: Main loop of system, called from the "main.py file"
    def start_trading(self, shared_status_variable, shared_asset_variable):
		
		#Try and catch for all the different functions in investment handler
        try:

			#If none of the other loops have collapsed we will continue the loop
            while shared_status_variable['rivh']:
                
                current_datetime = datetime.datetime.now()
								
				#We check our trading-schedule every five seconds (on mon-fri).
                if current_datetime.second % 5 == 0 and (current_datetime.weekday()!=self.SATURDAY and current_datetime.weekday()!=self.SUNDAY):
                    self.quant_view.check_trading_schedule(self, shared_status_variable, shared_asset_variable, current_datetime)
                    self.pp.pprint(shared_status_variable)
                    self.pp.pprint(shared_asset_variable)
                    sleep(1)
								
        except Exception as e:
            shared_status_variable['exception'] = str(traceback.format_exc()) #Find out cause of failure
            shared_status_variable['rivh'] = False #Now the other loops will also quit.		
	