import sqlite3

def create_table(db_name, sql):
	with sqlite3.connect(db_name) as db:
		cursor = db.cursor()
		cursor.execute(sql)
		db.commit()
		
if __name__ == "__main__":
	db_name = "lib/historical_prices.db"
	
	#ISIN = Tablename.
	sql = """create table SE0000108656
			(AID integer,
			isin text,
			identifier text,
			market_id integer,
			bid float,
			bid_volume float,
			ask float,
			ask_volume float,
			last float,
			bid1 float,
			bid_volume1 float,
			bid2 float,
			bid_volume2 float,
			bid3 float,
			bid_volume3 float,
			bid4 float,
			bid_volume4 float,
			bid5 float,
			bid_volume5 float,
			ask1 float,
			ask_volume1 float,
			ask2 float,
			ask_volume2 float,
			ask3 float,
			ask_volume3 float,
			ask4 float,
			ask_volume4 float,
			ask5 float,
			ask_volume5 float,
			time datetime,
			primary key(AID)
			)"""
	create_table(db_name, sql)
