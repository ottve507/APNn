from time import sleep
import datetime
import math
import logger as logger
import pandas as pd
import numpy as np
import investment_handler as investment_handler


class Quant_View:
	
	#Basic information for setting up
	BASIC_INFO = {'current_last': 0, 'current_ask': 0, 'current_ask_volume': 0, 'current_bid': 0, 'current_bid_volume': 0, 
	'bid1': 0.0, 'bid_volume1': 0, 'bid2': 0.0, 'bid_volume2': 0, 'bid3': 0.0, 'bid_volume3': 0, 'bid4': 0.0, 'bid_volume4': 0, 'bid5': 0.0, 'bid_volume5': 0,
	'ask1': 0.0, 'ask_volume1': 0, 'ask2': 0.0, 'ask_volume2': 0, 'ask3': 0.0, 'ask_volume3': 0, 'ask4': 0.0, 'ask_volume4': 0, 'ask5': 0.0, 'ask_volume5': 0,
	 'position_acq_price': 0, 'position_qty': 0}
	
	#Security measures for not buying too much (or little).
	MINIMUM_TRADE_VOLUME = 50000
	MAXIMUM_TRADE_VOLUME = 70000
	
	
	#initialize: Setup initial trade values
	def initialize(self, shared_asset_variable, loggervariable):
	
		#Setup traded asset (ericsson in this case...)	
		asset_identifier = {'isin': 'SE0000108656', 'identifier': '101', 'market_id':11} #(UID = identifier + market_id)
		asset_indicator = {'indicator': {'SMA5': 0.0, 'SMA10': 0.0, 'updated_at': datetime.datetime(2000,1,1,1,1,1,1)}}
		shared_asset_variable[asset_identifier['identifier']+str(asset_identifier['market_id'])] = dict(list(asset_identifier.items()) + list(self.BASIC_INFO.items()) + list(asset_indicator.items())) #combining the dicts
		
        #Set Variable for logging purposes
		self.loggervariable = loggervariable
	
	
	#check_trading_schedule: Runs every 5 second (set in investment_handler)
	def check_trading_schedule(self, investment_handler, shared_status_variable, shared_asset_variable, current_datetime):
	
		current_time = current_datetime.strftime("%H:%M")
	
		#EVENT #1
		#It's morning, let's start trading again (if it went below safety the day before)
		if current_time==investment_handler.RESET_LOSS_SAFETY and current_datetime.second % 100 == 0:
			shared_status_variable['stop_loss']['no_big_loss'] = True
			
			#Make sure we now a new day have started (sending e-mail)
			self.loggervariable.write_log("Good morning: We've started the initation of the trading day")
	
		#EVENT #2
		#If its in the morning or in the evening we will try to clear potential stuck orders
		if (current_time == investment_handler.CANCEL_MORNING_ORDERS or current_time == investment_handler.CANCEL_EVENING_ORDERS) and shared_status_variable['current_orders'] == True and current_datetime.second % 100 == 0:
			investment_handler.cancel_orders(shared_status_variable)			
			
		#EVENT #3
		#If it's end of trading hours, let's try to sell off some stuff. Fun time is over.
		if investment_handler.TRADE_HOURS_CLOSE<=current_time and current_time<investment_handler.CANCEL_EVENING_ORDERS and shared_status_variable['current_orders'] == False and shared_status_variable['have_positions'] == True:
			
			#We try to make sure that we get a sell order, but only try once a minute.
			if current_datetime.second % 100 == 0:
				
				#Trigger sell function... 
				for key in shared_asset_variable:
					why = "End of trade day" #sending message of why unexpected sale.
					investment_handler.end_of_day_sell(shared_status_variable, shared_asset_variable, key, why)
		
		#Housekeeping #1
		#Make sure we are logged in my touching the session every 2 min
		if current_datetime.minute % 2 == 0 and current_datetime.second % 100 == 0:
			investment_handler.check_if_logged_in(shared_status_variable)

		#Housekeeping #2
		#Stop-loss: If we loose more than 5%, stop trading...
		if current_datetime.minute % 2 == 0 and current_datetime.second % 100 == 0:
			investment_handler.check_stop_loss(shared_status_variable)
	

	#check_trading_strategy: Function that will run every time price depth is updated or when new historical data comes in.		
	def check_trading_strategy(self, investment_handler, shared_status_variable, shared_asset_variable, key):
		
		#First check if we have basic indicators to use
		if shared_asset_variable[key]['indicator']['SMA5'] != 0 and shared_asset_variable[key]['indicator']['SMA10'] != 0 and shared_asset_variable[key]['current_last']>=0:
		
			if shared_status_variable['have_positions'] == True and investment_handler.ok_to_trade(shared_status_variable, "SELL", shared_asset_variable, key):
				self.check_sell_price_and_volume(investment_handler, shared_status_variable, shared_asset_variable, key, 0, 1)
			
			elif shared_status_variable['have_positions'] == False and investment_handler.ok_to_trade(shared_status_variable, "BUY", shared_asset_variable, key):
				self.check_buy_price_and_volume(investment_handler, shared_status_variable, shared_asset_variable, key, 0, 1)	
			
						
	#check_sell_price_and_volume: Recursive selling strategy that will loop through the order book
	def check_sell_price_and_volume(self, investment_handler, shared_status_variable, shared_asset_variable, key, accumulated_vol, level):
		
		#Check bid price on level, will decrease each step.
		price_on_level = shared_asset_variable[key]['bid'+str(level)]
		
		#Check strategy and if it is enough volume to sell, otherwise call function again on next level
		if shared_asset_variable[key]['indicator']['SMA5'] > shared_asset_variable[key]['indicator']['SMA10'] and price_on_level >= shared_asset_variable[key]['indicator']['SMA5']:
			accumulated_vol += shared_asset_variable[key]['bid_volume'+str(level)]
			if accumulated_vol >= shared_asset_variable[key]['position_qty']:
				investment_handler.sell(shared_status_variable, shared_asset_variable, key, shared_asset_variable[key]['bid'+str(level)])
			elif level <= 4:
				self.check_sell_price_and_volume(investment_handler, shared_status_variable, shared_asset_variable, key, accumulated_vol, level+1)
	
	
	#check_sell_price_and_volume: Recursive selling strategy that will loop through the order book
	def just_sell(self, investment_handler, shared_status_variable, shared_asset_variable, key, accumulated_vol, level):
		
		#Check bid price on level, will decrease each step.
		price_on_level = shared_asset_variable[key]['bid'+str(level)]

		#Check strategy and if it is enough volume to sell, otherwise call function again on next level
		accumulated_vol += shared_asset_variable[key]['bid_volume'+str(level)]
		if accumulated_vol >= shared_asset_variable[key]['position_qty']:
			investment_handler.sell(shared_status_variable, shared_asset_variable, key, shared_asset_variable[key]['bid'+str(level)])
			self.loggervariable.write_important_message("Stop-loss sell")
		elif level <= 4:
			self.check_sell_price_and_volume(investment_handler, shared_status_variable, shared_asset_variable, key, accumulated_vol, level+1)

	
	#check_buy_price_and_volume: Recursive buying strategy that will loop through the order book
	def check_buy_price_and_volume(self, investment_handler, shared_status_variable, shared_asset_variable, key, accumulated_vol, level):
		
		#Check ask price on level, will increase each step.
		price_on_level = shared_asset_variable[key]['ask'+str(level)]
		
		#Check strategy and if it is enough volume to buy, otherwise call function again on next level
		if shared_asset_variable[key]['indicator']['SMA5'] < shared_asset_variable[key]['indicator']['SMA10'] and price_on_level <= shared_asset_variable[key]['indicator']['SMA5']:
			accumulated_vol += shared_asset_variable[key]['ask_volume'+str(level)]
			cost_of_purchase = accumulated_vol*price_on_level
			
			if cost_of_purchase >= self.MINIMUM_TRADE_VOLUME:
				investment_handler.buy(shared_status_variable, shared_asset_variable, key, price_on_level, accumulated_vol, self.MAXIMUM_TRADE_VOLUME)
			elif level <= 4:
				self.check_buy_price_and_volume(investment_handler, shared_status_variable, shared_asset_variable, key, accumulated_vol, level+1)
	
	
	#update_indicators: Function that will be run from the main loop. Indicator that can influence buying/selling
	def update_indicators(self, investment_handler, shared_status_variable, shared_asset_variable, current_time):

		#Get data for the past X min.
		X = 10 #(last 10 data points)
		
		#Loop through all the asset variables to check indicators
		for key in shared_asset_variable:
			df_asset_history = self.loggervariable.read_asset_history(shared_asset_variable, key, X)
			
			if(len(df_asset_history['last']))>X-1:

				#Set indicator updated at time
				shared_asset_variable[key]['indicator']['updated_at'] = current_time
				shared_asset_variable[key]['indicator']['SMA5'] = np.mean(df_asset_history['last'].iloc[-5:])
				shared_asset_variable[key]['indicator']['SMA10'] = np.mean(df_asset_history['last'].iloc[-10:])
			
				#Check trading strategy (once per asset)
				self.check_trading_strategy(investment_handler, shared_status_variable, shared_asset_variable, key)