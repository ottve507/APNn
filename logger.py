import smtplib
import datetime
import csv
import sqlite3
import datetime as dt
import time
import pandas as pd
import traceback

class Logger:
    
    
    #Constructor for setting up database location, e-mail address to use etc.
    def __init__(self, config):
        self.config = config
        self.from_addr_username = config['e-mail']['from_addr_username']
        self.from_addr_password = config['e-mail']['from_addr_password']
        self.from_addr_smtp = config['e-mail']['from_addr_smtp']
        self.to_addr = config['e-mail']['to_addr']
        self.database = config['history']['database']
        self.log = config['history']['log']
    
    
    #check_latest: Helper function to check if we already logged data for this time
    def check_latest(self, shared_asset_variable, key):

        #Find database to connect to
        db = sqlite3.connect(self.database)
        cursor = db.cursor()

        #Find current time (that should otherwise me logged)
        current_time = dt.datetime.now()

        df_return = pd.read_sql("select * from " + shared_asset_variable[key]['isin'] + " where time between :1 AND :2",db, params={"1":current_time.strftime('%Y-%m-%d %H:%M'), "2": current_time.strftime('%Y-%m-%d %H:%M')})

        #if panda empty we can return true (we can write history)
        if (df_return.empty):
            return True
        else:
            return False	


    #send_email: Sends email to check what has happened
    def send_email(self, message, receiver):
        print(message)
        msg = "\r\n".join([
        "Subject: Update! \n" ,
        message,
        ])
        server = smtplib.SMTP(self.from_addr_smtp)
        server.ehlo()
        server.starttls()
        server.login(self.from_addr_username,self.from_addr_password)
        server.sendmail(self.from_addr_username, receiver, msg)
        server.quit()


    #write_important_message: message that deserves extra attentions
    def write_important_message(self, message):
        self.send_email(message, self.from_addr_username) #send to own account
        self.send_email(message, self.to_addr) #send to important account (own)

        with open(self.log, 'a') as csvfile:
            fieldnames = ['time', 'message']
            datawriter = csv.DictWriter(csvfile, delimiter=',', fieldnames=fieldnames)

            #datawriter.writeheader()
            datawriter.writerow({'time': datetime.datetime.now(), 'message': message})


    #write_log: Send e-mail and write to log, called when major events happen
    def write_log(self, message):
        self.send_email(message, self.from_addr_username) #send to own account

        with open(self.log, 'a') as csvfile:
            fieldnames = ['time', 'message']
            datawriter = csv.DictWriter(csvfile, delimiter=',', fieldnames=fieldnames)

            #datawriter.writeheader()
            datawriter.writerow({'time': datetime.datetime.now(), 'message': message})


    #write_history: logging values, called from the main.py loop
    def write_history(self, shared_asset_variable):

        #Log with current hour and minute
        current_time = dt.datetime.now().strftime('%Y-%m-%d %H:%M')

        #Try inserting values into database, if it fails just continue but don't insert values in db...
        try:

            #Check that we haven't already logged this minute
            if self.check_latest(shared_asset_variable, list(shared_asset_variable.keys())[0]):

                #Find database to store values
                db = sqlite3.connect(self.database)
                cursor = db.cursor()

                #For each of the assets that we subscribe to, find right table and insert prices there
                for key in shared_asset_variable:	

                    #If we have a last value (i.e. there is data to put in), let's log, otherwise stop enter data.
                    if shared_asset_variable[key]['current_last'] > 0:

                        #log information for that asset!
                        sql = "insert into " + shared_asset_variable[key]['isin'] + " (isin, time, identifier, market_id, bid, bid_volume, ask, ask_volume, last, bid1, bid_volume1, bid2, bid_volume2, bid3, bid_volume3, bid4, bid_volume4, bid5, bid_volume5, ask1, ask_volume1, ask2, ask_volume2, ask3, ask_volume3, ask4, ask_volume4, ask5, ask_volume5) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                        cursor.execute(sql,(shared_asset_variable[key]['isin'], current_time, shared_asset_variable[key]['identifier'], shared_asset_variable[key]['market_id'], shared_asset_variable[key]['current_bid'], shared_asset_variable[key]['current_bid_volume'], shared_asset_variable[key]['current_ask'], shared_asset_variable[key]['current_ask_volume'], shared_asset_variable[key]['current_last'],
                            shared_asset_variable[key]['bid1'], shared_asset_variable[key]['bid_volume1'], shared_asset_variable[key]['bid2'], shared_asset_variable[key]['bid_volume2'], shared_asset_variable[key]['bid3'], shared_asset_variable[key]['bid_volume3'], shared_asset_variable[key]['bid4'], shared_asset_variable[key]['bid_volume4'], shared_asset_variable[key]['bid5'], shared_asset_variable[key]['bid_volume5'],
                            shared_asset_variable[key]['ask1'], shared_asset_variable[key]['ask_volume1'], shared_asset_variable[key]['ask2'], shared_asset_variable[key]['ask_volume2'], shared_asset_variable[key]['ask3'], shared_asset_variable[key]['ask_volume3'], shared_asset_variable[key]['ask4'], shared_asset_variable[key]['ask_volume4'], shared_asset_variable[key]['ask5'], shared_asset_variable[key]['ask_volume5']))

                    #If we don't have a last price, let's stop committing to database. 
                    else:
                        raise Exception("We don't have a last price to log")

                #If everything seems okay save to database
                db.commit()

        except Exception as e:
            self.write_log("Could not write to the database. This is the exception: " + str(e) + str(traceback.format_exc()))


    #read_history: read history from database. Only for subscribed assets
    def read_asset_history(self, shared_asset_variable, key, minutes):

        #Find database where to retrieve information
        db = sqlite3.connect(self.database)
        cursor = db.cursor()

        #Find period of how much data should be retrieved
        current_time = dt.datetime.now()
        current_time_w_lag = current_time-dt.timedelta(minutes=minutes)

        #Query database and return panda (dataframe)
        df_return = pd.read_sql("select * from " + shared_asset_variable[key]['isin'] + " where time between :1 AND :2",db, params={"1":current_time_w_lag.strftime('%Y-%m-%d %H:%M'), "2": current_time.strftime('%Y-%m-%d %H:%M')})

        return df_return