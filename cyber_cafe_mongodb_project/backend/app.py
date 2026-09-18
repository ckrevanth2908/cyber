import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId
from bson.errors import InvalidId

app = Flask(__name__)
CORS(app)

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("MONGODB_DB", "cyber_cafe_db")

if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI environment variable is missing.")

client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=8000)
db = client[DB_NAME]

customers = db.customers
terminals = db.terminals
rates = db.rates
sessions = db.sessions
transactions = db.transactions

customers.create_index([("created_at", DESCENDING)])
terminals.create_index([("terminal_no", ASCENDING)], unique=True)
sessions.create_index([("status", ASCENDING)])
transactions.create_index([("created_at", DESCENDING)])


def now():
    return datetime.now(timezone.utc)


def serialize(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    return value


def success(data=None, status=200):
    payload = {"success": True}
    if data is not None:
        payload["data"] = serialize(data)
    return jsonify(payload), status


def failure(message, status=400):
    return jsonify({"success": False, "error": message}), status


def body():
    return request.get_json(silent=True) or {}


def object_id(value, field):
    try:
        return ObjectId(str(value))
    except (InvalidId, TypeError):
        raise ValueError(f"{field} is invalid")


def positive_int(value, field):
    try:
        number = int(value)
        if number <= 0:
            raise ValueError
        return number
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a positive integer")


def nonnegative_number(value, field):
    try:
        number = Decimal(str(value))
        if number < 0:
            raise ValueError
        return float(number)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field} must be a non-negative number")


@app.get("/")
def home():
    return jsonify({
        "success": True,
        "message": "Cyber Cafe MongoDB API is running"
    })


@app.get("/api/health")
def health():
    try:
        client.admin.command("ping")
        return success({"status": "healthy", "database": DB_NAME})
    except Exception as exc:
        return failure(f"MongoDB connection failed: {exc}", 500)


@app.get("/api/dashboard")
def dashboard():
    try:
        total_customers = customers.count_documents({})
        total_terminals = terminals.count_documents({})
        available_terminals = terminals.count_documents({"status": "available"})
        occupied_terminals = terminals.count_documents({"status": "occupied"})
        active_sessions = sessions.count_documents({"status": "active"})

        revenue_rows = transactions.find({"status": "completed"}, {"amount": 1})
        total_revenue = sum(float(row.get("amount", 0)) for row in revenue_rows)

        return success({
            "total_customers": total_customers,
            "total_terminals": total_terminals,
            "available_terminals": available_terminals,
            "occupied_terminals": occupied_terminals,
            "active_sessions": active_sessions,
            "total_revenue": round(total_revenue, 2)
        })
    except Exception as exc:
        return failure(str(exc), 500)


@app.get("/api/customers")
def get_customers():
    try:
        data = list(customers.find().sort("created_at", DESCENDING))
        return success(data)
    except Exception as exc:
        return failure(str(exc), 500)


@app.post("/api/customers")
def add_customer():
    data = body()
    name = str(data.get("name", "")).strip()
    phone = str(data.get("phone", "")).strip()
    email = str(data.get("email", "")).strip()

    if not name:
        return failure("Customer name is required")

    document = {
        "name": name,
        "phone": phone or None,
        "email": email or None,
        "created_at": now()
    }

    try:
        result = customers.insert_one(document)
        document["_id"] = result.inserted_id
        return success(document, 201)
    except Exception as exc:
        return failure(str(exc), 500)


@app.get("/api/terminals")
def get_terminals():
    try:
        data = list(terminals.find().sort("terminal_no", ASCENDING))
        return success(data)
    except Exception as exc:
        return failure(str(exc), 500)


@app.post("/api/terminals")
def add_terminal():
    data = body()
    try:
        terminal_no = positive_int(data.get("terminal_no"), "terminal_no")
        document = {
            "terminal_no": terminal_no,
            "status": "available",
            "created_at": now()
        }
        result = terminals.insert_one(document)
        document["_id"] = result.inserted_id
        return success(document, 201)
    except Exception as exc:
        if "duplicate key" in str(exc).lower():
            return failure("Terminal number already exists", 409)
        return failure(str(exc), 400)


@app.get("/api/rates")
def get_rates():
    try:
        data = list(rates.find({"is_active": True}).sort("hourly_rate", ASCENDING))
        return success(data)
    except Exception as exc:
        return failure(str(exc), 500)


@app.post("/api/rates")
def add_rate():
    data = body()
    name = str(data.get("name", "")).strip()
    if not name:
        return failure("Rate name is required")
    try:
        hourly_rate = nonnegative_number(data.get("hourly_rate"), "hourly_rate")
        document = {
            "name": name,
            "hourly_rate": hourly_rate,
            "is_active": True,
            "created_at": now()
        }
        result = rates.insert_one(document)
        document["_id"] = result.inserted_id
        return success(document, 201)
    except ValueError as exc:
        return failure(str(exc))


@app.post("/api/sessions")
def start_session():
    data = body()
    try:
        customer_id = object_id(data.get("customer_id"), "customer_id")
        terminal_id = object_id(data.get("terminal_id"), "terminal_id")
        rate_id = object_id(data.get("rate_id"), "rate_id")
    except ValueError as exc:
        return failure(str(exc))

    customer = customers.find_one({"_id": customer_id})
    terminal = terminals.find_one({"_id": terminal_id})
    rate = rates.find_one({"_id": rate_id, "is_active": True})

    if not customer:
        return failure("Customer not found", 404)
    if not terminal:
        return failure("Terminal not found", 404)
    if not rate:
        return failure("Rate not found", 404)
    if terminal["status"] != "available":
        return failure("Terminal is already occupied", 409)
    if sessions.find_one({"terminal_id": terminal_id, "status": "active"}):
        return failure("Terminal already has an active session", 409)

    document = {
        "customer_id": customer_id,
        "terminal_id": terminal_id,
        "rate_id": rate_id,
        "start_time": now(),
        "status": "active"
    }

    result = sessions.insert_one(document)
    terminals.update_one({"_id": terminal_id}, {"$set": {"status": "occupied"}})
    document["_id"] = result.inserted_id
    return success(document, 201)


@app.get("/api/active-sessions")
def active_sessions():
    output = []
    for session in sessions.find({"status": "active"}).sort("start_time", DESCENDING):
        customer = customers.find_one({"_id": session["customer_id"]}, {"name": 1, "phone": 1})
        terminal = terminals.find_one({"_id": session["terminal_id"]}, {"terminal_no": 1})
        rate = rates.find_one({"_id": session["rate_id"]}, {"name": 1, "hourly_rate": 1})
        session["customer"] = customer or {}
        session["terminal"] = terminal or {}
        session["rate"] = rate or {}
        output.append(session)
    return success(output)


@app.post("/api/sessions/<session_id>/complete")
def complete_session(session_id):
    try:
        sid = object_id(session_id, "session_id")
    except ValueError as exc:
        return failure(str(exc))

    session = sessions.find_one({"_id": sid})
    if not session:
        return failure("Session not found", 404)
    if session["status"] != "active":
        return failure("Session is already completed", 409)

    end_time = now()
    start_time = session["start_time"]
    duration_hours = max((end_time - start_time).total_seconds() / 3600, 1 / 60)
    rate = rates.find_one({"_id": session["rate_id"]}) or {}
    amount = round(duration_hours * float(rate.get("hourly_rate", 0)), 2)

    sessions.update_one(
        {"_id": sid},
        {"$set": {
            "end_time": end_time,
            "duration_hours": round(duration_hours, 4),
            "amount": amount,
            "status": "completed"
        }}
    )
    terminals.update_one(
        {"_id": session["terminal_id"]},
        {"$set": {"status": "available"}}
    )

    transaction = {
        "session_id": sid,
        "customer_id": session["customer_id"],
        "amount": amount,
        "payment_method": str(body().get("payment_method", "cash")).lower(),
        "status": "completed",
        "created_at": end_time
    }
    transactions.insert_one(transaction)
    return success({"amount": amount, "duration_hours": round(duration_hours, 4)})


@app.get("/api/revenue")
def revenue():
    rows = list(transactions.find({"status": "completed"}).sort("created_at", DESCENDING))
    total = sum(float(row.get("amount", 0)) for row in rows)
    return success({"total_revenue": round(total, 2), "transactions": rows})


def seed_data():
    if terminals.count_documents({}) == 0:
        terminals.insert_many([
            {"terminal_no": number, "status": "available", "created_at": now()}
            for number in range(1, 11)
        ])
    if rates.count_documents({}) == 0:
        rates.insert_one({
            "name": "Standard",
            "hourly_rate": 30.0,
            "is_active": True,
            "created_at": now()
        })


seed_data()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
