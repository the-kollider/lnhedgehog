## LN Hedgehog 🦔⚡

Locking in a fiat value of your lightning wallet balance whilst earning interest using the Kollider api.

#### Whats the point?

Locking up Bitcoin in lightning channels is fine as long as the market goes up. However, as soon as the Bitcoin price starts to go sideways or even down the cost of capital is usually higher than your return. In these times you ideally want to be able to 

1. Earn interest on your locked Bitcoin
2. Protect yourself from dowside risk (market going down)

This is what Hedgehog tying to achieve.

#### How does it work?

In a nutshell Hedgehog looks at your channel balances and automatically short sells Bitcoin against the fiat currency of your choice (currently only USD). This means that the value **in fiat terms** of your channel balances will always be the same no matter whether Bitcoin goes up or down. You might be thinking now that in order to do that you would need to lock up your entire channel balance on Kollider, which means you cannot spend your lightning Bitcoin. Fortunately this is not the case because Kollider allows you to borrow funds to limit your exposure on the plaform. For example, by default Hedgehog uses 10% of your balance to perform the hedging trade which leaves you with 90% of your lightning bitcoin free to spend.

Furthermore, since hedging is done through a perpetual swap contract where interest rates are exchange between buyers and sellers every 8h, Hedgehog can accumulate interest on your locked balance. However, in times where there is significant downwards pressure this hedging strategy will become more expensive.

## Installation
#### Install LND dependencies
```shell
bash install_lnd_deps.sh
```
This will install the python libraries required to commuincate to the LND RPC as well as download and compile the lates protobuf files from LND.

#### Installing Kollider dependencies

```shell
git clone https://github.com/kolliderhq/kollider-api-client.git
cd kollider_api_client
pip install -e .
```

## Run 

```shell
python main.py
```

## ⚠️ Warning

This is still under construction and shall not be used in production. **DO NOT USE IN PRODUCTION**
