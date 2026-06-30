import pandas as pd
import numpy as np
import sqlite3
#data laoding

customers = pd.read_csv('users_data.csv')
card_info = pd.read_csv('cards_data.csv')
transactions = pd.read_csv('transactions_data.csv')
transactions = transactions.sample(n=500000, random_state=42)  # keep 500k rows


#some feature engineering
def data_clean(transactions, customers, card_info):
    transactions=transactions.drop_duplicates()
    customers=customers.drop_duplicates()
    card_info=card_info.drop_duplicates()
    transactions['date'] = pd.to_datetime(transactions['date'])
    return transactions, customers, card_info 
    
    

transactions, customers, card_info = data_clean(transactions, customers, card_info)

#data_merging
df=transactions.merge(card_info, on=['card_id', 'customer_id'], how='left')
df=df.merge(customers, on='customer_id', how='left')
df=df.sort_values(by=['card_id', 'date']) #reset_index(0, drop=True)
df['amount'] = df['amount'].str.replace(r'[^0-9.]', '', regex=True).astype(float)
df['amount'] = df['amount'].fillna(0)

def detect_fraud_engine(df):
#high value check
    df['high_value'] = df['amount'] > 1000
#count how many transacations per card in the last hour
    df=df.set_index('date')
    df['transaction_count_last_hour'] = df.groupby('card_id').rolling('1h')['id'].count().reset_index(0, drop=True)
    df['rule_high_velocity']=df['transaction_count_last_hour']>5
#combine rules
    df['potential_fraud'] = df['high_value'] | df['rule_high_velocity']
    return df

df = detect_fraud_engine(df)



#the data is ready to be loaded into a database
connection=sqlite3.connect('fraud_detection.db')
cursor=connection.cursor()

customer_table_query = '''create table if not exists customers
 (customer_id integer primary key, current_age integer,address text,gender )'''
cursor.execute(customer_table_query)

card_table_query='''create table if not exists cards(
card_id text primary key,card_type text,card_number text,expires text,cvv integer )'''
cursor.execute(card_table_query)

fact_table_query='''create table if not exists transaction_facts
(id integer primary key,card_id text,customer_id integer,amount integer,date text,
high_value boolean,transaction_count_last_hour integer,rule_high_velocity boolean,
potential_fraud boolean,
foreign key(card_id) references cards(card_id),
foreign key(customer_id) references customers(customer_id))'''

cursor.execute(fact_table_query)

customer_final=customers[['customer_id', 'current_age', 'address','gender']].drop_duplicates()
card_final=card_info[['card_id','card_type','card_number','expires','cvv']].drop_duplicates()


transactions_final = df[[
    'id', 'card_id', 'customer_id', 'amount',
    'high_value', 'transaction_count_last_hour', 'rule_high_velocity', 'potential_fraud'
]]#.copy()

# Pull date from the index, cast to string, and place it back in order
transactions_final['date'] = transactions_final.index.astype(str)
transactions_final = transactions_final[[
    'id', 'card_id', 'customer_id', 'amount', 'date',
    'high_value', 'transaction_count_last_hour', 'rule_high_velocity', 'potential_fraud'
]]

cursor.executemany('''insert or replace into customers values
(?, ?, ?, ?)''',customer_final.values.tolist())


cursor.executemany('''insert or replace into cards values
(?, ?, ?, ?, ?)''',card_final.values.tolist())


cursor.executemany('''insert or replace into transaction_facts values
(?, ?, ?, ?, ?, ?, ?, ?, ?)''',transactions_final.values.tolist())


connection.commit()
connection.close()