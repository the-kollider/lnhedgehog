import lightning_pb2 as ln
import lightning_pb2_grpc as lnrpc
import grpc
import os
import codecs
import threading
from time import sleep

os.environ["GRPC_SSL_CIPHER_SUITES"] = 'HIGH+ECDSA'

class LndClient(object):
	def __init__(self, node_url, macaroon_path, tls_path):

		cert = open(os.path.expanduser(tls_path), 'rb').read()
		creds = grpc.ssl_channel_credentials(cert)
		channel = grpc.secure_channel(node_url, creds)
		self.stub = lnrpc.LightningStub(channel)

		with open(os.path.expanduser(macaroon_path), 'rb') as f:
			macaroon_bytes = f.read()
			self.macaroon = codecs.encode(macaroon_bytes, 'hex')
		self.node_url = node_url

	def get_info(self):
		return self.stub.GetInfo(ln.GetInfoRequest(), metadata=[('macaroon', self.macaroon)])

	def get_onchain_balance(self):
		return self.stub.WalletBalance(ln.WalletBalanceRequest(), metadata=[('macaroon', self.macaroon)])

	def get_channel_balances(self):
		return self.stub.ChannelBalance(ln.ChannelBalanceRequest(), metadata=[('macaroon', self.macaroon)])

	def send_payment(self, payment_request):
		send_request = ln.SendRequest(payment_request=payment_request)
		return self.stub.SendPaymentSync(send_request, metadata=[('macaroon', self.macaroon)])

	def add_invoice(self, amount, memo):
		invoice = ln.Invoice(value=amount, memo=memo)
		return self.stub.AddInvoice(invoice, metadata=[('macaroon', self.macaroon)])

	def start(self):
		self.wst = threading.Thread(
            target=self.update_state)
		self.wst.daemon = True
		self.wst.start()

	def update_state(self):
		pass

if __name__ in "__main__":
	node_url = "10.0.1.7:10009"
	macaroon_path = "admin.macaroon"
	tls_path = "tls.cert"
	lnd_cli = LNDClient(node_url, macaroon_path, tls_path)
	lnd_cli.start()
	while True:
		sleep(1)
