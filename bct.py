
import pdb
import time
from operator import itemgetter
from math import exp

class trade_engine:
	def __init__(self):
		#configurable variables
		self.shares = 0.1 		#order size
		self.wll = 180			#window length long
		self.wls = 2		#window length short
		self.buy_wait = 0		#min sample periods between buy orders
		self.buy_wait_after_stop_loss = 6	#min sample periods between buy orders
							#after a stop loss order
		self.markup = 0.01		#order mark up
		self.stop_loss = 0.282		#stop loss
		self.stop_age = 10000		#stop age - dump after n periods
		self.macd_buy_trip = -0.66	#macd buy indicator
		self.min_i_pos = 0		#min periods of increasing price
						#before buy order placed
		
		self.min_i_neg = 0		#min periods of declining price
						#before sell order placed
		
		self.stbf = 1.97		#short trade biasing factor
						#-- increase to favor day trading
						#-- decrease to 1 to eliminate bias
		
		self.commision = 0.0# 0.0065	#mt.gox commision
		
		self.quartile = 1		#define which market detection quartile to trade on (1-4)
		self.market_class = []
		self.reset()
		return

	def reset(self):
		#metrics and state variables
		self.history = []			#moving window of the inputs
		self.period = 0				#current input period
		self.time = 0				#current period timestamp
		self.input_log = []			#record of the inputs
		self.wl_log = []			#record of the wl
		self.ws_log = []			#record of the ws
		self.macd_pct_log = []
		self.buy_log = []
		self.sell_log = []
		self.stop_log = []
		self.net_worth_log = []
		self.balance = 1000			#account balance
		self.opening_balance = self.balance	#record the starting balance
		self.score_balance = 0			#cumlative score
		self.buy_delay = 0		#delay buy counter
		self.buy_delay_inital = self.buy_delay	#delay buy counter
		self.macd_pct = 0			
		self.macd_abs = 0
		self.avg_wl = 0
		self.avg_ws = 0
		self.ema_short = 0
		self.ema_long = 0
		self.i_pos = 0				#periods of increasing price
		self.i_neg = 0				#periods of decreasing price
		self.positions_open = []		#open order subset of all trade positions
		self.positions = []			#all trade positions
		self.metric_macd_pct_max = -10000	#macd metrics
		self.metric_macd_pct_min = 10000
		self.wins = 0
		self.loss = 0
		self.order_history = "NOT GENERATED"
		return
	
	def test_quartile(self,quartile):
		#valid inputs are 1-4
		self.quartile = quartile / 4.0
	
	def classify_market(self,input_list):
		#print "start market classify"
		#market detection preprocessor splits the input data into 
		#quartiles based on the true range indicator

		self.market_class = []
		atr_depth = 60 * 4 #4 hour atr
		
		#print "calc the true pct range indicator"
		last_t = 0
		last_tr = 0
		for i in range(len(input_list)):
			t,p = input_list[i]
			t = int(t * 1000) 
			if i > atr_depth + 1:
				dsp = [r[1] for r in input_list[i - atr_depth - 1:i]]	#get the price data set
				dsp_min = min(dsp)
				dsp_max = max(dsp)
				tr = (dsp_max - dsp_min) / dsp_min #put in terms of pct chg
				self.market_class.append([t,tr])
				last_t = t
				last_tr = tr
			else:
				#pad out the data
				self.market_class.append([t,0])

		#pad the end of the data to support future order testing
		for i in range(10):
			self.market_class.append([t,tr])

		"""
		#now find the quartiles from a historgram
		print "hist"
		length = len(self.market_class)
		l = [r[1] for r in self.market_class]
		hist = dict((p,l.count(p)) for p in set(l))
		keys = hist.keys()
		keys.sort()
		total = 0
		last_key = ""
		target = 0.25
		quartiles = []
		print "searching quartiles"
		for key in keys:
			total += hist[key]
			if total / float(length) > target:
				print target,last_key
				quartiles.append(last_key)
				target += 0.25
			last_key = key
			if target == 1.0:
				break
		"""
		#I was overthinking again...
		quartiles = []
		l = [r[1] for r in self.market_class]
		l.sort()
		quartiles.append(l[int(len(l) * 0.25)])
		quartiles.append(l[int(len(l) * 0.50)])
		quartiles.append(l[int(len(l) * 0.75)])

		#and apply them to the market class log
		for i in range(len(self.market_class)):
			p = self.market_class[i][1]
			self.market_class[i][1] = 0.25
			if p > quartiles[0]:
				self.market_class[i][1] = 0.50
			if p > quartiles[1]:
				self.market_class[i][1] = 0.75
			if p > quartiles[2]:
				self.market_class[i][1] = 1.0
			if i < atr_depth + 1:
				self.market_class[i][1] = 0.0	#ignore early (uncalculated) data 

		#print "end market classify"

		#debug!!
		#self.net_worth_log = self.market_class

	def metrics_report(self):
		m = ""
		m += "\nShares: " + str(self.shares)
		m += "\nMarkup: " + str(self.markup * 100) + "%"
		m += "\nStop Loss: " + str(self.stop_loss * 100) + "%"
		m += "\nStop Age: " + str(self.stop_age)
		m += "\nBuy Delay: " + str(self.buy_wait)
		m += "\nBuy Delay After Stop Loss: " + str(self.buy_wait_after_stop_loss)
		m += "\nMACD Trigger: " + str(self.macd_buy_trip) + "%"
		m += "\nEMA Window Long: " + str(self.wll)
		m += "\nEMA Window Short: " + str(self.wls)
		m += "\niPos: " + str(self.i_pos)
		m += "\niNeg: " + str(self.i_neg)
		m += "\nShort Trade Bias: " + str(self.stbf)
		m += "\nCommision: " + str(self.commision * 100) + "%"
		m += "\nScore: " + str(self.score())
		m += "\nTotal Periods : " + str(self.period)
		m += "\nInitial Buy Delay : " + str(self.buy_delay_inital)
		m += "\nOpening Balance: $" + str(self.opening_balance)
		m += "\nClosing Balance: $" + str(self.balance)
		m += "\nTransaction Count: " + str(len(self.positions))
		m += "\nWin: " + str(self.wins)
		m += "\nLoss: " + str(self.loss)
		try:
			m += "\nWin Pct: " + str(100 * (self.wins / float(self.wins + self.loss))) + "%"
		except:
			pass
		m += "\nMACD Max Pct: " + str(self.metric_macd_pct_max)+ "%"
		m += "\nMACD Min Pct: " + str(self.metric_macd_pct_min)+ "%"
		return m
	
	def dump_open_positions(self):
		#dump all active trades to get a current balance
		self.positions_open = [] #clear out the subset buffer
		for position in self.positions:
			if position['status'] == "active":
				position['status'] = "dumped"
				position['actual'] = self.history[1]	#HACK! go back in time one period to make sure we're using a real price
									#and not a buy order target from the reporting script.
				position['sell_period'] = self.period
				self.balance += position['actual'] * (position['shares'] - (position['shares'] * self.commision))
			if position['age'] > 0:
				self.score_balance += ((position['actual'] * (position['shares'] - (position['shares'] * self.commision))) / (position['buy'] * position['shares'])) * (pow(position['age'],self.stbf) / position['age'] )

	def score(self):
		self.dump_open_positions()
		if (self.wins + self.loss) > 0:	    
			self.positions = sorted(self.positions, key=itemgetter('buy_period'))
			#use the last position buy_period to calc the exp_scale. If the total input period counts are used the scores will
			#change with new price data regardless if the trade history remains unchanged. This would effectivly disable local optima detection
			exp_scale = 1 / float(self.positions[-1]['buy_period'])	
			final_score_balance = self.score_balance
			for p in self.positions:
				if p['status'] == "sold":
					p['age'] = float(p['age'])
					p['score'] = (((p['target'] - p['buy']) / p['buy']) * 100.0 ) * self.shares
					#apply non-linear scaling to the trade based on the round trip time (age)
					#favors a faster turn around time on positions
					p['score'] /= (pow(p['age'],self.stbf) / p['age'] )
					p['score'] *= 100.0
					if p['age'] < 2.0:
						p['score'] *= 0.3 #I'm knocking down 1min trades because theres a chance the system will miss them
				if p['status'] == "stop":
					if p['actual'] > p['buy']: #only add stop orders to the score if there was a loss
						p['score'] = (((p['actual'] - p['buy']) / p['buy']) * 100.0)  * self.shares
				#apply e^0 to e^1 weighting to favor the latest trade results
				p['score'] *= exp(exp_scale * p['buy_period']) 
				final_score_balance += p['score']

			final_score_balance += self.buy_wait / 1000.0
			final_score_balance += self.buy_wait_after_stop_loss / 1000.0
			final_score_balance -= self.stop_loss / 10.0
			final_score_balance += (self.wls / 10000.0)
			final_score_balance -= (self.stop_age / 1000.0)
			#final_score_balance += self.markup / 10000.0

			final_score_balance *= self.wins / (self.wins + self.loss * 1.0)
			final_score_balance *= self.markup
			final_score_balance += self.shares

			if self.opening_balance > self.balance:
				#losing strategy
				final_score_balance -= 5000 #999999999
		else:
			#no trades generated
			final_score_balance = -0.123456789

		return final_score_balance

	def ai(self):
		#decrement the buy wait counter
		if self.buy_delay > 0:
			self.buy_delay -= 1
		#place buy orders, set price targets and stop loss limits
		current_price = self.history[0]
		#if the balance is sufficient to place an order and there is no buy delay
		buy = current_price * -1
		if self.balance > (current_price * self.shares) and self.buy_delay == 0 and self.quartile == self.market_class[self.period][1]:
			if self.macd_pct < self.macd_buy_trip:
				#set delay until next buy order
				self.buy_delay = self.buy_wait
				self.balance -= (current_price * self.shares)
				actual_shares  = self.shares - (self.shares * self.commision)
				buy = current_price
				target = (buy * self.markup) + buy
				stop = buy - (buy * self.stop_loss)
				self.buy_log.append([self.time,buy])

				new_position = {'master_index':len(self.positions),'age':0,'buy_period':self.period,'sell_period':0,'trade_pos': self.balance,'shares':actual_shares,'buy':buy,'cost':self.shares*buy,'target':target,'stop':stop,'status':"active",'actual':0,'score':0}
				self.positions.append(new_position.copy())
				#maintain a seperate subset of open positions to speed up the search to close the open positions
				#after a long run there may be thousands of closed positions 
				#it was killing performance searching all of them for the few open positions at any given time
				self.positions_open.append(new_position.copy()) 
				
		
		current_net_worth = 0
		
		#check for sold and stop loss orders
		sell = current_price * -1
		stop = current_price * -1
		updated = False
		for position in self.positions_open:
			if position['status'] == "active" and position['target'] <= current_price: #and self.i_neg >= self.min_i_neg:
				updated = True
				position['status'] = "sold"
				position['actual'] = current_price
				sell = current_price
				position['sell_period'] = self.period
				self.wins += 1
				self.balance += position['target'] * (position['shares'] - (position['shares'] * self.commision))
				self.score_balance += ((position['target'] * (position['shares'] - (position['shares'] * self.commision))) / (position['buy'] * position['shares'])) * (pow(position['age'],self.stbf) / position['age'] )
				#update the position in the master list
				buy_period = position['buy_period']
				#self.positions = filter(lambda x: x.get('buy_period') != buy_period, self.positions) #delete the old record
				#self.positions.append(position.copy()) #and add the updated record
				self.positions[position['master_index']] = position.copy()
			elif position['status'] == "active" and (position['stop'] >= current_price or position['age'] >= self.stop_age):
				updated = True
				position['status'] = "stop"
				position['actual'] = current_price
				stop = current_price
				position['sell_period'] = self.period
				if position['stop'] >= current_price:
					self.loss += 1
					self.buy_delay += self.buy_wait_after_stop_loss
				else:
					self.win += current_price / position['target'] 

				self.balance += position['actual'] * (position['shares'] - (position['shares'] * self.commision))
				self.score_balance += ((position['actual'] * (position['shares'] - (position['shares'] * self.commision))) / (position['buy'] * position['shares'])) * (pow(position['age'],self.stbf) / position['age'] )
				#update the position in the master list
				buy_period = position['buy_period']
				#self.positions = filter(lambda x: x.get('buy_period') != buy_period, self.positions) #delete the old record
				#self.positions.append(position.copy()) #and add the updated record
				self.positions[position['master_index']] = position.copy()
				
			elif position['status'] == "active":
				#position remains open, capture the current value
				current_net_worth += current_price * (position['shares'] - (position['shares'] * self.commision))
				position['age'] += 1

		#remove any closed positions from the open position subset
		if updated == True:
			self.positions_open = filter(lambda x: x.get('status') == 'active', self.positions_open)

		#add the balance to the net worth
		current_net_worth += self.balance
		
		self.net_worth_log.append([self.time,current_net_worth])
		if sell > 0:
			self.sell_log.append([self.time,sell])
		if stop > 0:
			self.stop_log.append([self.time,stop])
		return
	
	def macd(self):
		#wait until there is enough data to fill the moving windows
		if len(self.history) == self.wll:
			s = 0
			l = 0
			
			#calculate the ema weighting multipliers
			ema_short_mult = (2.0 / (self.wls + 1) )
			ema_long_mult = (2.0 / (self.wll + 1) )
			
			#bootstrap the ema calc using a simple moving avg if needed
			if self.ema_long == 0:
				for i in range(self.wll):
					if i < self.wls:
						s += self.history[i]
						l += self.history[i]
				self.avg_ws = s / self.wls
				self.avg_wl = l / self.wll
				self.ema_long = self.avg_wl
				self.ema_short = self.avg_ws
			else:
				#calculate the long and short ema
				self.ema_long = (self.history[0] - self.ema_long) * ema_long_mult + self.ema_long
				self.ema_short = (self.history[0] - self.ema_short) * ema_short_mult + self.ema_short
			
			
			#calculate the absolute and pct differences between the
			#long and short emas
			self.macd_abs = self.ema_short - self.ema_long
			self.macd_pct = (self.macd_abs / self.ema_short) * 100
			
		
	
			#track the number of sequential positive and negative periods
			if self.history[0] - self.history[1] > 0:
				self.i_neg = 0
				self.i_pos += 1
			if self.history[0] - self.history[1] < 0:
				self.i_pos = 0
				self.i_neg += 1
		
			#track the max & min macd pcts (metric)
			if self.macd_pct > self.metric_macd_pct_max:
				self.metric_macd_pct_max = self.macd_pct
			if self.macd_pct < self.metric_macd_pct_min:
				self.metric_macd_pct_min = self.macd_pct
		else:
			self.ema_short = self.history[0]
			self.ema_long = self.history[0]
			self.macd_pct = 0

		#log the indicators
		self.macd_pct_log.append([self.time,self.macd_pct])
		self.wl_log.append([self.time,self.ema_long])
		self.ws_log.append([self.time,self.ema_short])
		
		
	def display(self):
		#used for debug
		print ",".join(map(str,[self.history[0],self.macd_pct,self.buy_wait]))
	
	def input(self,time_stamp,record):
		#self.time = int(time.mktime(time.strptime(time_stamp))) * 1000
		self.time = int(time_stamp * 1000) 
		self.input_log.append([self.time,record])
		
		###Date,Sell,Buy,Last,Vol,High,Low,###
		self.history.insert(0,record)
		if len(self.history) > self.wll:
			self.history.pop()	#maintain a moving window of
					#the last wll records
		self.macd()		#calc macd
		self.ai()		#call the trade ai
		self.period += 1	#increment the period counter
		#self.display()
		return

	def log_orders(self,filename=None):
		""" old method:
		self.order_history = ""
		if filename != None:
			f = open(filename,'w')
		for position in self.positions:
			if filename != None:
				f.write("-"*40 + "\n")
			self.order_history += "-"*40 + "\n"
			for key in position.keys():
				if filename != None:
					f.write(key + "," + str(position[key]) + "\n")
				self.order_history += key + "," + str(position[key]) + "\n"
		if filename != None:
			f.close()
		"""

		self.order_history = ""
		self.positions = sorted(self.positions, key=itemgetter('buy_period'),reverse=True)
		if len(self.positions) > 0:
			keys = self.positions[0].keys()
		#write the header
		self.order_history = "<table class='imgtbl'>\n"
		self.order_history +="<tr>"
		for key in keys:
			self.order_history +="<th>%s</tht>"%key
		self.order_history +="</tr>\n"
		for p in self.positions:
			self.order_history +="<tr>"
			for key in keys:
				if p.has_key(key):
					if p['status']=='stop':
						color = 'r'
					elif p['status']=='dumped':
						color = 'y'
					elif p['status']=='sold':
						color = 'g'
					else:
						color = 'b'
					self.order_history +="<td class='%s'>"%color
					if type(p[key]) == type(1.0):
						self.order_history += "%.2f"% round(p[key],2)				
					else:	
						self.order_history += str(p[key])
					self.order_history +="</td>"
				else:
					self.order_history +="<td>N/A</td>"

			self.order_history +="</tr>\n"	
		self.order_history += "</table>"
		return
	
	def log_transactions(self,filename):
		#log the transactions to a file
		#used with excel / gdocs to chart price and buy/sell indicators
		f = open(filename,'w')
		
		for i in range(len(self.input_log)):
			for position in self.positions:
				if position['buy_period'] == i:
					#print position['buy_period'],i
					self.input_log[i].append('buy')
					self.input_log[i].append(position['sell_period'] - position['buy_period'])
					self.input_log[i].append(position['status'])
					self.input_log[i].append(i)
				if position['sell_period'] == i:
					self.input_log[i].append('sell')
					self.input_log[i].append('0')
					self.input_log[i].append(position['status'])
					self.input_log[i].append(i)
			r = ",".join(map(str,self.input_log[i]))
			f.write(r)
			f.write('\n')
		f.close()
		return

	def compress_log(self,log):
		#removes records with no change in price, before and after record n
		ret_log = []
		for i in range(len(log)):
			if i > 1 and i < len(log) - 2:
				if log[i-1][1] == log[i][1] and log[i+1][1] == log[i][1]:
					pass #no change before or after, omit record
				else:
					ret_log.append(log[i])
			else:
				ret_log.append(log[i])

		return ret_log

	def chart(self,template,filename,periods=-1):
		self.log_orders()
		
		f = open(template,'r')
		tmpl = f.read()
		f.close()
		
		if periods < 0:
			periods = self.period * -1
		else:
			periods *= -1
		
		#print "chart: compressing data"
		wl = str(self.compress_log(self.wl_log[periods:])).replace('L','')
		ws = str(self.compress_log(self.ws_log[periods:])).replace('L','')
		macd_pct = str(self.compress_log(self.macd_pct_log[periods:])).replace('L','')
		input = str(self.compress_log(self.input_log[periods:])).replace('L','')
		net_worth = str(self.compress_log(self.net_worth_log[periods:])).replace('L','')
		volatility_quartile = str(self.compress_log(self.market_class[periods:])).replace('L','')

		buy = str([])
		sell = str([])
		stop = str([])
		
		if periods == self.period:
			buy = str(self.buy_log[periods:]).replace('L','')
			sell = str(self.sell_log[periods:]).replace('L','')
			stop = str(self.stop_log[periods:]).replace('L','')
		else:
			#get the timestamp for the start index
			time_stamp = self.input_log[periods:periods+1][0][0]
			#search the following for the time stamp
			for i in range(len(self.buy_log)):
				if self.buy_log[i][0] >= time_stamp:
					buy = str(self.buy_log[i:]).replace('L','')
					break
			for i in range(len(self.sell_log)):
				if self.sell_log[i][0] >= time_stamp:
					sell = str(self.sell_log[i:]).replace('L','')
					break
			for i in range(len(self.stop_log)):
				if self.stop_log[i][0] >= time_stamp:
					stop = str(self.stop_log[i:]).replace('L','')
					break

		#print "chart: filling the template"
		tmpl = tmpl.replace("{PRICES}",input)
		tmpl = tmpl.replace("{WINDOW_LONG}",wl)
		tmpl = tmpl.replace("{WINDOW_SHORT}",ws)
		tmpl = tmpl.replace("{MACD_PCT}",macd_pct)
		tmpl = tmpl.replace("{BUY}",buy)
		tmpl = tmpl.replace("{SELL}",sell)
		tmpl = tmpl.replace("{STOP}",stop)
		tmpl = tmpl.replace("{NET_WORTH}",net_worth)
		tmpl = tmpl.replace("{METRICS_REPORT}",self.metrics_report().replace('\n','<BR>'))
		#tmpl = tmpl.replace("{ORDERS_REPORT}",self.order_history)
		tmpl = tmpl.replace("{VOLATILITY_QUARTILE}",volatility_quartile)


 		#print "chart: writing the data to a file"
		f = open(filename,'w')
		f.write(tmpl)
		f.close()
		return



def test():
	te = trade_engine()
	#set the trade engine class vars

	te.shares = 0.1
	te.wll = 242
	te.wls = 1
	te.buy_wait = 0
	te.markup = 0.01
	te.stop_loss = 0.128
	te.stop_age = 2976
	te.macd_buy_trip = -0.02
	te.min_i_neg = 2
	te.min_i_pos = 0
	te.buy_wait_after_stop_loss = 0

	for row in d[1:]:
		r = row.split(',')[1] #last
		t = row.split(',')[0] #time
		te.input(float(t),float(r))

	return te


if __name__ == "__main__":

    __appversion__ = "0.02a"
    print "Bitcoin trade simulator v%s"%__appversion__
    
    
    #open the history file
    f = open("./datafeed/bcfeed_mtgoxUSD_1min.csv",'r')
    d = f.readlines()
    f.close()


    import hotshot,hotshot.stats
    prof = hotshot.Profile("bct.prof")

    te = prof.runcall(test)
    prof.close()
    stats = hotshot.stats.load("bct.prof")
    stats.strip_dirs()
    stats.sort_stats('time','calls')
    stats.print_stats(20)


    print "Score:",te.score()
    print "Closing Balance:",te.balance
    print "Transaction Count: ",len(te.positions)

    te.log_transactions('transactions.csv')
    te.log_orders('orders.csv')
    te.chart("/home/emfb/public_html/bc/chart.templ","/home/emfb/public_html/bc/chart_test.html")
