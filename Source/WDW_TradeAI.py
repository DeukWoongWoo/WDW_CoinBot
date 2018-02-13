import constants as cons
#import threading
from poloniex_api import poloniex
from DW_ChartData import ChartData
#import numpy as np
import time
import datetime

class DW_TradeAI:
	def __init__(self):
		self.api = poloniex(cons.API_KEY, cons.SECRET)
		self.isTrade = False
		self.isBuy = False
		self.amount = self.api.returnBalances()[cons.TRADE_COIN]
		print("Amount : "+str(self.amount))
		logTime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		print("Start Time : "+logTime)

	def GetTradeCoin(self):
		tradeCoin = cons.TRADE_COIN

		json24hVolume = self.api.return24hVolume()

		maxVolume=0
		maxKey=""

		for data in json24hVolume:
			if (data[:3] == tradeCoin):
				volume = float(json24hVolume[data][tradeCoin])
				if(volume > maxVolume):
					maxKey = data
					maxVolume = volume

		return maxKey

	def GetRate(self, coin):
		jsonOrderBook = self.api.returnOrderBook(coin)
		sellOrder = jsonOrderBook['asks'][0][0]
		buyOrder = jsonOrderBook['bids'][0][0]
		#myOrder = (float(sellOrder)+float(buyOrder))/2
		return (sellOrder, buyOrder)

	def trunc(self, amount):
		return round((float(amount)-0.000000005),9)

	def GetBuyAmount(self, price, amount):
		return round(self.trunc(float(amount)/price),9)

	def DoBuy(self, coin, rate, amount):
		print("DoBuy...")
		#self.price = (float(rate[0])+float(rate[1]))/2
		self.price=round(float(rate[1]),9)+0.00000002
		print("price = "+str(self.price)+" rate = "+str(rate))
		buyAmount = self.GetBuyAmount(self.price, amount)
		print(buyAmount)
		buyResult = self.api.buy(coin, self.price, buyAmount)
		print(buyResult)
		orderNumber = buyResult['orderNumber']
		#print(orderNumber)
		return orderNumber

	def DoSell(self, coin, isMargin, kindOfCoin):
		print("Do Sell...")
		amount = self.api.returnBalances()[kindOfCoin[1]]
		rate = self.GetRate(coin)
		sellResult = self.api.sell(coin, float(rate[1]), amount)
		orderNumber = sellResult['orderNumber']
		print("Sell Order Number : "+str(orderNumber))
		margin = (float(rate[1])-self.price)/self.price * 100

		while True:
			jsonOpenOrder = self.api.returnOpenOrders(coin)
			print("Sell OpenOrder : "+str(jsonOpenOrder))
			if len(jsonOpenOrder) == 0 :
				self.isBuy = False
				self.isTrade = False
				self.SaveLog("Sell"+isMargin, float(rate[1]), kindOfCoin, round(self.trunc(self.price*float(amount)),9), amount, margin)
				nextCoin = self.CheckCoin(coin)
				break

		return nextCoin


	def SaveLog(self, tradeType, rate, coin, amount1, amount2, margin=0):
		logDate = datetime.datetime.now().strftime("%Y%m%d")
		logTime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		f = open("log_"+logDate+".txt",'a')
		f.write("["+tradeType+"] "+logTime+" rate = "+str(round(rate,9))+" "+coin[0]+" = "+str(amount1)+" "+coin[1]+" = "+str(amount2)+" Margin : "+str(round(margin,2))+"\n")
		f.close()

	def CheckCoin(self, coin):
		newCoin = self.GetTradeCoin()
		kindOfCoin = str(newCoin).split('_')
		if coin != newCoin:
			chartData = ChartData(self.api, newCoin, cons.CHART_PERIODS[0])
		
		print("Next Coin : "+newCoin)
		return newCoin, kindOfCoin

	def run(self):
		tradeCoin = self.GetTradeCoin()
		kindOfCoin = str(tradeCoin).split('_')
		chartData = ChartData(self.api, tradeCoin, cons.CHART_PERIODS[0])

		print("TradeCoin : "+str(tradeCoin)+"\n")
		while True:
			chartResult = chartData.update()

			if not self.isBuy and self.isTrade and chartResult >= 0:
				print("Buy Timing...")
				amount = self.api.returnBalances()[kindOfCoin[0]]
				print("chartResult = "+str(chartResult*100000)+" amount = "+str(amount)+"\n")
				rate = self.GetRate(tradeCoin)
				orderNumber = self.DoBuy(tradeCoin, rate, amount)
				#print(type(orderNumber))
				#total = buyResult['resultingTrades'][0]['total']
				orderTime = time.time()
				count=7
				while True:
					jsonOpenOrder = self.api.returnOpenOrders(tradeCoin)
					print(str(jsonOpenOrder))
					if len(jsonOpenOrder) == 0 :
						print("Buy Complete...")
						self.isBuy = True
						self.SaveLog(" Buy ", self.price, kindOfCoin, amount, self.GetBuyAmount(self.price, amount))
						break
					reRate = self.GetRate(tradeCoin)
					if rate[1] != reRate[1] :
						print("Buy Cancel and Next Process...")
						isCancel = self.api.cancel(tradeCoin, orderNumber)
						print("Buy Cancel : "+str(isCancel))
						if isCancel == 0:
							break

						amount = self.api.returnBalances()[kindOfCoin[0]]
						print("Buy Remain : "+str(amount))
						if float(amount) < 0.0001 :
							continue
						ret = chartData.update()
						if ret < 0 :
							amount = self.api.returnBalances()[kindOfCoin[1]]
							if float(amount) > 0.0001:
								tradeCoin , kindOfCoin = self.DoSell(tradeCoin, "%", kindOfCoin)
							else:
								self.isTrade = False
								self.isBuy = False
							break

						#diff = round(self.trunc(ret),9) - round(self.trunc(chartResult),9)
						#compare = diff/round(self.trunc(chartResult),9)*100
						#if time.time() - orderTime < 60:
						if count > 0:
							orderNumber = self.DoBuy(tradeCoin, reRate, amount)
							count=count-1
						
						else:
							print("Buy Give up...")
							amount = self.api.returnBalances()[kindOfCoin[1]]
							if float(amount) > 0.0001:
								tradeCoin , kindOfCoin = self.DoSell(tradeCoin, "%", kindOfCoin)
							else:
								self.isTrade = False
								self.isBuy = False
							break

			elif self.isBuy:
				print("Sell Timing...")
				print(tradeCoin)

				isMargin="+"
				margin=0
				checkMargin=0.5
				flagMargin=1
				while True:
					rate = self.GetRate(tradeCoin)
					margin = (float(rate[1])-self.price)/self.price * 100
					if margin > checkMargin*flagMargin:
						flagMargin=flagMargin+1
						print("Current Margin : "+str(margin))
					elif margin < checkMargin*(flagMargin-1):
						flagMargin=flagMargin-1
						print("Current Margin : "+str(margin))

					if float(margin) >= float(cons.MARGIN) : #or margin <= -1.5:
						isMargin="+"
						print("Plus Margin...")
						break
					
					ret = chartData.update()
					if ret < 0:
						isMargin="-"
						print("Minus Margin...")
						break

				print("Sell Get Margin...")
				tradeCoin , kindOfCoin = self.DoSell(tradeCoin, isMargin, kindOfCoin)


			elif not self.isTrade and chartResult < 0:
				print("isTrade True... MACD-Signal = "+str(chartResult))
				self.isTrade = True
				
			elif self.isTrade and chartResult > 0:
				print("isTrade False... MACD-Signal = "+str(chartResult))
				self.isTrade = False
