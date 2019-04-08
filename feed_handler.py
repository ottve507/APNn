import json
import socket, ssl, pprint
import http.client
from time import sleep
import investment_handler as investment_handler
import logger as logger
import traceback
import quant_view as quant_view


#start_private_feed: Looping, checking the socket of the private feed 
def start_private_feed(session_key, private_feed_hostname, private_feed_port, investment_handler, shared_status_variable, shared_asset_variable):
	
	try:
		#Create SSL-wrapped socket
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		ssl_socket = ssl.wrap_socket(s)
		
		#Connect to socket
		ssl_socket.connect((private_feed_hostname, private_feed_port))
		
		#Send session key to start feed
		cmd = json.dumps({'cmd': 'login', 'args': {'session_key': session_key, 'service': 'NEXTAPI'}})
		cmdj=str.encode(cmd + "\n")
		ssl_socket.write(cmdj)
		
		#While ['rprf'] we will continue the software
		while shared_status_variable['rprf']:
			out=ssl_socket.read(2048)
			outs=out.decode(encoding='UTF-8')
			
			#There might be multiple json in same string
			outs_split = outs.splitlines()
			
			#Loop through the "potential" list of Json-objects
			for j_s in outs_split:
				
				#Check if something is wrong with the json message, otherwise just skip it...
				try:					
					out_json = json.loads(j_s)
				except Exception as e:
					#Just continue, nothing to do
					continue
						
				#Check if order comes in and is pending. Then we have pending orders.
				if 'action_state' in out_json and out_json['action_state'] == 'INS_PEND':
					shared_status_variable['current_orders'] = True
			
				#Check if a trade is made, then we can update or portfolio
				elif 'type' in out_json and out_json['type'] == 'trade':
					if 'data' in out_json and 'volume' in out_json['data'] and out_json['data']['volume']>0:
					
						#ID to find asset
						key = out_json['data']['tradable']['identifier']+str(out_json['data']['tradable']['market_id'])
					
						if out_json['data']['side'] == 'BUY':
							shared_asset_variable[key]['position_qty']+=out_json['data']['volume'] 				
							shared_asset_variable[key]['position_acq_price']=out_json['data']['price']['value']			
							shared_status_variable['have_positions'] = True
						elif out_json['data']['side'] == 'SELL':
							shared_asset_variable[key]['position_qty']-=out_json['data']['volume'] 				
							shared_asset_variable[key]['position_acq_price']=0
							investment_handler.check_if_we_have_positions(shared_status_variable, shared_asset_variable) #If multiple traded assets, we need to loop
			
				#Check if an order was deleted, then we should not have any pending orders.
				elif 'data' in out_json and 'order_state' in out_json['data'] and out_json['data']['order_state'] == 'DELETED':
					shared_status_variable['current_orders'] = False
				
				#Log what is happening with the trades...
				if 'type' in out_json and out_json['type'] != 'heartbeat':
					logger.write_log("From private feed: " + str(out_json))
	
	except Exception as e:
		shared_status_variable['rprf'] = False
		shared_status_variable['exception'] = str(traceback.format_exc())


#start_public_feed: Keeps track of the stocks we subscribe to
def start_public_feed(session_key, public_feed_hostname, public_feed_port, investment_handler, quant_view, shared_status_variable, shared_asset_variable):
	
	try:
		#Create SSL-wrapped socket
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		ssl_socket = ssl.wrap_socket(s)
		
		#Connect to socket
		ssl_socket.connect((public_feed_hostname, public_feed_port))
		
		#Send session key
		cmd = json.dumps({'cmd': 'login', 'args': {'session_key': session_key, 'service': 'NEXTAPI'}})
		cmdj=str.encode(cmd + "\n")
		ssl_socket.write(cmdj)
		
		#Clean current price subscription
		for key in shared_asset_variable:
			unsubscibe = json.dumps({'cmd': 'unsubscribe', 'args': {'t': 'price', 'i': shared_asset_variable[key]['identifier'], 'm': shared_asset_variable[key]['market_id']}})
			cmdj=str.encode(unsubscibe + "\n")
			ssl_socket.write(cmdj)
		
		#Subscripe to current price
		for key in shared_asset_variable:
			subscibe = json.dumps({'cmd': 'subscribe', 'args': {'t': 'price', 'i': shared_asset_variable[key]['identifier'], 'm': shared_asset_variable[key]['market_id']}})
			cmdj=str.encode(subscibe + "\n")
			ssl_socket.write(cmdj)
			
		#Clean current depth subscription
		for key in shared_asset_variable:
			unsubscibe = json.dumps({'cmd': 'unsubscribe', 'args': {'t': 'depth', 'i': shared_asset_variable[key]['identifier'], 'm': shared_asset_variable[key]['market_id']}})
			cmdj=str.encode(unsubscibe + "\n")
			ssl_socket.write(cmdj)

		#Subscripe to current depth
		for key in shared_asset_variable:
			subscibe = json.dumps({'cmd': 'subscribe', 'args': {'t': 'depth', 'i': shared_asset_variable[key]['identifier'], 'm': shared_asset_variable[key]['market_id']}})
			cmdj=str.encode(subscibe + "\n")
			ssl_socket.write(cmdj)
		
		#Start public feed loop
		while shared_status_variable['rpuf']:
			out=ssl_socket.read(4096)
			outs=out.decode(encoding='UTF-8')
			
			#There might be multiple json in same string
			outs_split = outs.splitlines()
			
			#Loop through the "potential" list of Json-objects
			for j_s in outs_split:
				
				#Check if something is wrong with the json message, otherwise just skip it...
				try:					
					out_json = json.loads(j_s)
				except Exception as e:
					#Log what has happened
					logger.write_log(str(e) + "Faulty message trying to be parsed" + str(outs))
					continue
				
				#If there is an update in price, update all the info in shared variable.
				if "type" in out_json and out_json['type'] == 'price' and "data" in out_json and "i" in out_json['data'] and "m" in out_json['data']:
			
					key = out_json['data']['i']+str(out_json['data']['m'])
						
					if "ask" in out_json['data']:
						shared_asset_variable[key]['current_ask'] = out_json['data']['ask']
				
					if "ask_volume" in out_json['data']:
						shared_asset_variable[key]['current_ask_volume'] = out_json['data']['ask_volume']
				
					if "bid" in out_json['data']:
						shared_asset_variable[key]['current_bid'] = out_json['data']['bid']
				
					if "bid_volume" in out_json['data']:
						shared_asset_variable[key]['current_bid_volume'] = out_json['data']['bid_volume']
				
					if "last" in out_json['data']:
						shared_asset_variable[key]['current_last'] = out_json['data']['last']
				
				#If there is an update in order depth, update shared_variable and check our strategy.
				elif "type" in out_json and out_json['type'] == 'depth' and "data" in out_json and "i" in out_json['data'] and "m" in out_json['data']:
			
					key = out_json['data']['i']+str(out_json['data']['m'])
			
					if "ask1" in out_json['data']:
						shared_asset_variable[key]['ask1'] = out_json['data']['ask1']
				
					if "ask_volume1" in out_json['data']:
						shared_asset_variable[key]['ask_volume1'] = out_json['data']['ask_volume1']
				
					if "ask2" in out_json['data']:
						shared_asset_variable[key]['ask2'] = out_json['data']['ask2']

					if "ask_volume2" in out_json['data']:
						shared_asset_variable[key]['ask_volume2'] = out_json['data']['ask_volume2']
				
					if "ask3" in out_json['data']:
						shared_asset_variable[key]['ask3'] = out_json['data']['ask3']

					if "ask_volume3" in out_json['data']:
						shared_asset_variable[key]['ask_volume3'] = out_json['data']['ask_volume3']
				
					if "ask4" in out_json['data']:
						shared_asset_variable[key]['ask4'] = out_json['data']['ask4']

					if "ask_volume4" in out_json['data']:
						shared_asset_variable[key]['ask_volume4'] = out_json['data']['ask_volume4']

					if "ask5" in out_json['data']:
						shared_asset_variable[key]['ask5'] = out_json['data']['ask5']

					if "ask_volume5" in out_json['data']:
						shared_asset_variable[key]['ask_volume5'] = out_json['data']['ask_volume5']	
				
					if "bid1" in out_json['data']:
						shared_asset_variable[key]['bid1'] = out_json['data']['bid1']

					if "bid_volume1" in out_json['data']:
						shared_asset_variable[key]['bid_volume1'] = out_json['data']['bid_volume1']
				
					if "bid2" in out_json['data']:
						shared_asset_variable[key]['bid2'] = out_json['data']['bid2']

					if "bid_volume2" in out_json['data']:
						shared_asset_variable[key]['bid_volume2'] = out_json['data']['bid_volume2']
				
					if "bid3" in out_json['data']:
						shared_asset_variable[key]['bid3'] = out_json['data']['bid3']

					if "bid_volume3" in out_json['data']:
						shared_asset_variable[key]['bid_volume3'] = out_json['data']['bid_volume3']

					if "bid4" in out_json['data']:
						shared_asset_variable[key]['bid4'] = out_json['data']['bid4']

					if "bid_volume4" in out_json['data']:
						shared_asset_variable[key]['bid_volume4'] = out_json['data']['bid_volume4']
				
					if "bid5" in out_json['data']:
						shared_asset_variable[key]['bid5'] = out_json['data']['bid5']

					if "bid_volume5" in out_json['data']:
						shared_asset_variable[key]['bid_volume5'] = out_json['data']['bid_volume5']
			
					#With new price information, check strategy (commented, might be too much checking...)
					#quant_view.check_trading_strategy(investment_handler, shared_status_variable, shared_asset_variable, key)
					
	except Exception as e:
		shared_status_variable['rpuf'] = False
		shared_status_variable['exception'] = str(traceback.format_exc())
	
