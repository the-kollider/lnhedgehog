from rich.console import Console
from rich.table import Column, Table
from utils import sats_to_dollars

def print_node_info(ctx):
	console = Console()
	node_info = ctx["node_info"]
	table = Table(show_header=False)
	table.add_column("Title1", style="dim", width=32)
	table.add_column("Title")
	is_connected = node_info is not None
	if is_connected:
		table.add_row(
    		"Connected", "True", style="green"
		)
	else:
		table.add_row(
    		"Connected", "False"
		)
	table.add_row(
		"alias",
		node_info["alias"]
		)
	table.add_row(
		"pubkey",
		node_info["identity_pubkey"]
		)
	table.add_row(
		"Number of Channels",
		str(node_info["num_active_channels"])
		)
	console.print(table)

def print_wallet_info(ctx):
	console = Console()
	wallet = ctx["wallet"]
	current_index_price = ctx["current_index_price"]

	table = Table(show_header=True)
	table.add_column("Account", style="dim", width=32)
	table.add_column("Balance in Sats")
	table.add_column("Balance in USD")

	channel_balance_usd = int(wallet["channel_balance"] / 100000000 * current_index_price * 1000) / 1000
	onchain_balance_usd = int(wallet["onchain_balance"] / 100000000 * current_index_price * 1000) / 1000
	kollider_balance_usd = int(wallet["kollider_balance"] / 100000000 * current_index_price * 1000) / 1000

	total_balance = wallet["channel_balance"] + wallet["onchain_balance"] + wallet["kollider_balance"]
	total_balance_usd = int(total_balance / 100000000 * current_index_price * 1000) / 1000

	table.add_row(
		"Channel Balance ⚡",
		str(int(wallet["channel_balance"])),
		"$ " + str(channel_balance_usd),
		style="#ffff00"
		)
	table.add_row(
		"Onchain Balance 🔗",
		str(wallet["onchain_balance"]),
		"$ " + str(onchain_balance_usd),
		style="#FFA500"
		)
	table.add_row(
		"Kollider Balance",
		str(int(wallet["kollider_balance"])),
		"$ " + str(kollider_balance_usd)
		)
	table.add_row(
		"Total Balance",
		str(total_balance),
		"$ " + str(total_balance_usd),
		style="bold green"
		)
	console.print(table)


def print_status(ctx):
	console = Console()
	last_state = ctx["last_state"]

	table = Table(show_header=False)
	table.add_column("", style="dim", width=32)
	table.add_column("")

	is_locked = not last_state["is_locking"]
	color = "green" if is_locked else "red"
	if last_state["lock_price"] is None:
		table.add_row(
			"Price Locked",
			str(is_locked) + " 🔓",
			style=color
			)
	else:
		table.add_row(
			"Price Locked",
			str(is_locked) + " 🔒",
			style=color
			)

	table.add_row(
		)

	table.add_row(
		"Locked Price",
		"$ " + str(last_state["lock_price"]),
		)

	table.add_row(
		"Current Index Price",
		"$ " + str(ctx["current_index_price"]),
		)

	table.add_row(
		"Locked Proporiton",
		str(ctx["hedge_proportion"] * 100) + "%",
		)

	table.add_row(
		"Locked Value in Sats (Notional)",
		str(int(last_state["target_value"])) + " Sats",
		)

	dollar_value = sats_to_dollars(last_state["target_value"], ctx["current_index_price"])
	table.add_row(
		"Locked Value in USD (Notional)",
		"$ " + str(dollar_value),
		)

	console.print(table)


def print_success(value):
	console = Console()
	console.print("OK", style="green")
	console.print("{}".format(value))



