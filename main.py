import requests, yaml, datetime, time

'''
Questions for client:
1) Does court matter?
3) How does drop work
4) Normally get 3ds?
5) Price limit?
'''

try:
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
except Exception as e:
    input(f"Unable to read config file {e}")

class main:
    def __init__(self):
        self.sesh = requests.session()
        self.sesh.headers.update({
            "Accept-Language": "en",
            "X-Requested-With": "com.playtomic.app 5.115.0",
            "User-Agent": "Android 11",
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip, deflate, br"
        })
    
    def print(self, text, colour="green"):
        print(f"{datetime.datetime.now().strftime('%H:%M:%S')} | {text}")
    
    def wait_for_drop(self, drop_date_time):
        self.print(f"Waiting until {drop_date_time} for drop...")
        while True:
            if datetime.datetime.now() >= drop_date_time: 
                return True
            time.sleep(0.5)

    def login(self):
        r = self.sesh.post("https://api.playtomic.io/v3/auth/login", json={"email":config["email"],"password":config["password"]})

        if r.status_code == 200:
            self.print("Logged in", colour="yellow")
            self.sesh.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
        else:
            self.print(f"Error logging in {r.status_code} {r.text}", colour="red")
            raise RuntimeError("Fatal error logging in")
        
    def find_club(self, search_text):
        r = self.sesh.get(f"https://api.playtomic.io/v1/tenants?playtomic_status=ACTIVE&tenant_name={search_text}")
        
        if len(r.json()) == 0:
            self.print(f"No clubs found with that name", colour="red")
            raise RuntimeError("Fatal error finding club")
        
        club = r.json()[0]
        tenant_id = club["tenant_id"]

        self.print(f"Found club {club['tenant_name']} with id {tenant_id}")

        return tenant_id
    

    def get_courts(self, tenant_id="da7718de-43b3-11e8-8674-52540049669c"):
        r = self.sesh.get(f"https://api.playtomic.io/v1/tenants/{tenant_id}")
        courts = r.json()["resources"]
        return courts
   
    def atc(self, tenant_id="da7718de-43b3-11e8-8674-52540049669c", resource_id="7fe0a82a-5edb-43e6-acca-75edc9861cca", start="2024-08-14T18:45:00", duration=75):
        for i in range(10):
            r = self.sesh.post("https://api.playtomic.io/v1/payment_intents",
                json={
                    "allowed_payment_method_types":["OFFER","CASH","WALLET","MERCHANT_WALLET","DIRECT","SWISH_STRIPE","IDEAL","BANCONTACT","PAYTRAIL","CREDIT_CARD","PAYPAL","QUICK_PAY"],
                    "user_id":"me",
                    "cart":{
                        "requested_item":{
                            "cart_item_type":"CUSTOMER_MATCH",
                            "cart_item_data":{
                                "tenant_id":tenant_id,
                                "resource_id":resource_id,
                                "start":start,
                                "duration":duration,
                                "user_id":"me",
                                "match_registrations":[{"user_id":"me","pay_now":True}],
                                "supports_split_payment":True,
                                "number_of_players":4
                            }
                        }
                    },
                    "pay_later_supported":False
                })
            if r.status_code == 409:
                self.print(f"Booking not available, retrying... {r.text}", colour="red")
                time.sleep(1)

            elif r.status_code == 200:
                payment_intent_id = r.json()["payment_intent_id"]
                first_payment_id = [x for x in r.json()["available_payment_methods"] if x["method_type"] in ["CREDIT_CARD", "MERCHANT_WALLET"]][0]["payment_method_id"]
                self.print("Booking in cart, checking out...")
                return payment_intent_id, first_payment_id
            
            else:
                self.print(f"Unable to book {r.status_code} {r.text}", colour="red")
                raise RuntimeError("Fatal error, unable to book")
        
        self.print("Tried to book 10 times, quitting", colour="red")
        raise RuntimeError("Fatal error, unable to book in 10 trys")
        
    
    def set_payment_method(self, payment_intent_id="b8d1efae-a01f-4096-93e9-83c87acd7499", first_payment_id="CREDIT_CARD-STRIPE_404384db-6b9c-4de9-8f63-767c26e9389e"):
        r = self.sesh.patch(f"https://api.playtomic.io/v1/payment_intents/{payment_intent_id}",
            json={
                "selected_payment_method_id":first_payment_id,
                "selected_payment_method_data":{
                    "stripe_return_url":f"playtomic://new-payments/stripe?anemone_payment_intent_id={payment_intent_id}"
                }
            }
        )
        if r.status_code == 200:
            self.print("Set payment method", colour="green")
            return
        else:
            self.print(f"Error setting payment method {r.status_code} {r.text}")
            raise RuntimeError("Fatal error setting card")
    
    def submit_order(self, payment_intent_id="b8d1efae-a01f-4096-93e9-83c87acd7499"):
        r = self.sesh.post(f"https://api.playtomic.io/v1/payment_intents/{payment_intent_id}/confirmation",
            json={}               
            )
        
        if r.status_code != 200:
            self.print(f"Error submitting order {r.status_code} {r.text}", colour="red")
            raise RuntimeError("Fatal error submitting order")

        if r.json()["status"] == "SUCCEEDED":
            self.print(f"Reservation successful!", colour="green")
            return
        
        elif r.json()["status"] == "REQUIRES_PAYMENT_METHOD_ACTION":
            self.print(f"Control - Click the link to complete order {r.json()['next_payment_action_data']['stripe_next_action']['value']['url']}", colour="magenta")
            return

def run():
    date = input("What date would you like to book for? (eg 2024-08-14) ")

    drop_time = config["booking_opens_time_local"]
    drop_date_time = datetime.datetime.strptime(f"{date}T{drop_time}", "%Y-%m-%dT%H:%M") - datetime.timedelta(days=config["book_days_before"])

    inst = main()
    inst.login()
    tenant_id = inst.find_club(config["club_name"])

    courts = inst.get_courts(tenant_id=tenant_id)
    court_index = config["court_number"] -1
    date_time_for_booking = f"{date}T{config['booking_time_utc']}:00"
    duration = config["booking_duration"]
    resource_id = courts[court_index]["resource_id"]
    court_name = courts[court_index]["name"]

    inst.print(f"Booking {court_name} at {date_time_for_booking} for {duration} minutes")

    inst.wait_for_drop(drop_date_time)

    inst.login()
    payment_intent_id, first_payment_id = inst.atc(tenant_id=tenant_id, resource_id=resource_id, start=date_time_for_booking, duration=duration)
    inst.set_payment_method(payment_intent_id=payment_intent_id, first_payment_id=first_payment_id)
    inst.submit_order(payment_intent_id=payment_intent_id)


if __name__ == "__main__":
    try:
        run()
        input("Program complete, you can now close")
    except Exception as e:
        input(e)