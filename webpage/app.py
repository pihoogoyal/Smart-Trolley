import paho.mqtt.client as mqtt
from flask import Flask, jsonify, render_template
from flask_cors import CORS
import threading
import json

# ML imports
import pandas as pd
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import apriori, association_rules

app = Flask(__name__)
CORS(app)

# GLOBAL DATA STORE
datastore = []
lastdata = ""

# LOAD DATA
with open("data.json") as f:
    transactions = json.load(f)

# ML TRAINING (Apriori)
te = TransactionEncoder()
te_data = te.fit(transactions).transform(transactions)
df = pd.DataFrame(te_data, columns=te.columns_)

print("Transactions:", transactions)
print("DataFrame:\n", df.head())

# frequent_itemsets = apriori(df, min_support=0.2, use_colnames=True)
frequent_itemsets = apriori(df, min_support=0.05, use_colnames=True)

print("Frequent itemsets:\n", frequent_itemsets)

if not frequent_itemsets.empty:
    rules = association_rules(frequent_itemsets, metric="confidence", min_threshold=0.3)
else:
    rules = []

# ML SUGGESTION FUNCTION
def get_ml_suggestion(item):
    suggestions = []

    for _, row in rules.iterrows():
        if item in row['antecedents']:
            for i in row['consequents']:
                suggestions.append(i)

    if suggestions:
        return "👉 You may also like: " + ", ".join(list(set(suggestions))[:3])

    return ""


# MQTT CONNECT
def on_connect(client, userdata, flags, rc):
    print("MQTT Connected:", rc)
    client.subscribe("smart/trolley")


# MQTT RECEIVE
def on_message(client, userdata, msg):
    global lastdata

    try:
        data = msg.payload.decode()

        if data == lastdata:
            return

        lastdata = data

        print("Received:", data)

        item_name = data.split(",")[0]
        suggestion = get_ml_suggestion(item_name)

        datastore.append({
            "item": data,
            "suggestion": suggestion
        })

    except Exception as e:
        print("Error:", e)


# MQTT THREAD (UNCHANGED)
def start_mqtt():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect("broker.hivemq.com", 1883, 60)
    client.loop_forever()


threading.Thread(target=start_mqtt, daemon=True).start()


# CACHE FIX
@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


# ROUTES (UNCHANGED)
@app.route('/')
def home():
    return render_template("index.html")

@app.route('/data')
def get_data():
    return jsonify(datastore)


# RUN
if __name__ == '__main__':
    print("🚀 Backend Running...")
    app.run(debug=True)