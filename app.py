from dotenv import load_dotenv
from ml_model.predict import predict_product
from flask import Flask, render_template, request, redirect, url_for, session

import mysql.connector

import os
import base64
import mimetypes

import requests

from werkzeug.utils import secure_filename

from datetime import date, datetime



load_dotenv()







NYCKEL_CLIENT_ID = os.getenv("NYCKEL_CLIENT_ID")

NYCKEL_CLIENT_SECRET = os.getenv("NYCKEL_CLIENT_SECRET")

NYCKEL_FUNCTION_ID = os.getenv("NYCKEL_FUNCTION_ID")



print("Client ID loaded:", bool(os.getenv("NYCKEL_CLIENT_ID")))

print("Client Secret loaded:", bool(os.getenv("NYCKEL_CLIENT_SECRET")))

print("Function ID:", os.getenv("NYCKEL_FUNCTION_ID"))

app = Flask(__name__)
app.secret_key = "scanSure_secret_key"



def get_nyckel_token():
    """Request an access token from Nyckel using credentials in .env."""
    if not NYCKEL_CLIENT_ID or not NYCKEL_CLIENT_SECRET:
        raise ValueError(
            "Nyckel credentials are missing in the .env file."
        )

    response = requests.post(
        "https://www.nyckel.com/connect/token",
        data={
            "grant_type": "client_credentials",
            "client_id": NYCKEL_CLIENT_ID,
            "client_secret": NYCKEL_CLIENT_SECRET,
        },
        timeout=30,
    )

    # Show the actual response if Nyckel rejects the request.
    if not response.ok:
        raise ValueError(
            f"Nyckel token error {response.status_code}: "
            f"{response.text}"
        )

    token_data = response.json()
    token = token_data.get("access_token")

    if not token:
        raise ValueError("Nyckel did not return an access token.")

    return token


def check_product_with_ai(image_path):
    """Send the uploaded product image to Nyckel and return its prediction."""
    if not NYCKEL_FUNCTION_ID:
        raise ValueError("NYCKEL_FUNCTION_ID is missing in the .env file.")

    token = get_nyckel_token()

    mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
    if not mime_type.startswith("image/"):
        mime_type = "image/jpeg"

    with open(image_path, "rb") as image_file:
        encoded_image = base64.b64encode(
            image_file.read()
        ).decode("utf-8")

    image_data = f"data:{mime_type};base64,{encoded_image}"

    response = requests.post(
        f"https://www.nyckel.com/v1/functions/{NYCKEL_FUNCTION_ID}/invoke",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"data": image_data},
        timeout=60,
    )

    response.raise_for_status()
    prediction = response.json()

    label = str(prediction.get("labelName", "")).strip()
    if not label:
        raise ValueError(
            "Nyckel response did not include a prediction label."
        )

    confidence_value = float(prediction.get("confidence", 0))
    confidence = round(
        max(0.0, min(1.0, confidence_value)) * 100
    )

    normalized_label = label.lower()

    if any(
        word in normalized_label
        for word in ("counterfeit", "fake", "not genuine")
    ):
        result = "Fake"
    elif any(
        word in normalized_label
        for word in ("genuine", "authentic", "real")
    ):
        result = "Genuine"
    else:
        result = "Pending"

    return result, confidence, label





# =========================================================

# UPLOAD FOLDER

# =========================================================



UPLOAD_FOLDER = "static/uploads"



app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER



os.makedirs(UPLOAD_FOLDER, exist_ok=True)





# =========================================================

# MYSQL DATABASE CONNECTION

# =========================================================



db = mysql.connector.connect(

    host="localhost",

    user="root",

    password="",

    database="scansure"

)





# =========================================================

# GLOBAL TEMPLATE CONTEXT

# Makes shared navbar/sidebar values available on EVERY page.

# This prevents UndefinedError for unread_count on any tab.

# =========================================================



@app.context_processor

def inject_global_template_values():

    context = {

        "unread_count": 0,

        "name": session.get("user_name", session.get("admin_name", "User")),

        "email": session.get("user_email", session.get("admin_email", ""))

    }



    # Only fetch notifications for a logged-in user.

    user_id = session.get("user_id")

    if user_id is not None:

        cursor = None

        try:

            # Reconnect if MySQL dropped the connection between requests.

            db.ping(reconnect=True, attempts=3, delay=1)

            cursor = db.cursor(dictionary=True, buffered=True)

            cursor.execute(

                """

                SELECT COUNT(*) AS unread_count

                FROM notifications

                WHERE user_id = %s

                  AND is_read = FALSE

                """,

                (user_id,)

            )

            row = cursor.fetchone()

            if row:

                context["unread_count"] = int(row.get("unread_count") or 0)

        except Exception as error:

            # Keep the page renderable even if notification count cannot load.

            app.logger.warning("Could not load unread notification count: %s", error)

            context["unread_count"] = 0

        finally:

            if cursor is not None:

                try:

                    cursor.close()

                except Exception:

                    pass



    return context





# =========================================================

# ADMIN LOGIN CREDENTIALS

# =========================================================



ADMIN_EMAIL = "admin_scansure@gmail.com"

ADMIN_PASSWORD = "Admin@123"





# =========================================================

# HOME

# =========================================================



@app.route("/")

def home():

    return redirect("/login")





# =========================================================

# LOGIN

# =========================================================



@app.route("/login", methods=["GET", "POST"])

def login():



    if request.method == "POST":



        email = request.form.get("email", "").strip()

        password = request.form.get("password", "").strip()



        # -------------------------------------------------

        # ADMIN LOGIN

        # -------------------------------------------------



        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:



            session.clear()



            session["admin_logged_in"] = True

            session["admin_email"] = ADMIN_EMAIL

            session["admin_name"] = "Admin"



            return redirect("/admin_dashboard")



        # -------------------------------------------------

        # USER LOGIN

        # -------------------------------------------------



        cursor = db.cursor(dictionary=True)



        cursor.execute(

            """

            SELECT *

            FROM users

            WHERE email = %s

            AND password = %s

            """,

            (email, password)

        )



        user = cursor.fetchone()



        cursor.close()



        if user:



            session.clear()



            session["user_id"] = user["id"]

            session["user_name"] = user["name"]

            session["user_email"] = user["email"]



            return redirect("/user_dashboard")



        return "Invalid Email or Password"



    return render_template("login.html")





# =========================================================

# REGISTER

# =========================================================



@app.route("/register", methods=["GET", "POST"])

def register():



    if request.method == "POST":



        name = request.form.get("name", "").strip()

        email = request.form.get("email", "").strip()

        password = request.form.get("password", "")



        cursor = db.cursor(dictionary=True)



        cursor.execute(

            """

            SELECT *

            FROM users

            WHERE email = %s

            """,

            (email,)

        )



        existing_user = cursor.fetchone()



        if existing_user:



            cursor.close()



            return "Email already registered!"



        cursor.execute(

            """

            INSERT INTO users

            (name, email, password)

            VALUES (%s, %s, %s)

            """,

            (name, email, password)

        )



        db.commit()



        user_id = cursor.lastrowid



        cursor.close()



        session.clear()



        session["user_id"] = user_id

        session["user_name"] = name

        session["user_email"] = email



        return redirect("/user_dashboard")



    return render_template("register.html")





# =========================================================

# USER DASHBOARD

# =========================================================



@app.route("/user_dashboard")

def user_dashboard():



    if "user_id" not in session:

        return redirect("/login")



    user_id = session["user_id"]



    cursor = db.cursor(dictionary=True)



    # -------------------------------------------------

    # PRODUCT SCANS

    # -------------------------------------------------



    cursor.execute(

        """

        SELECT *

        FROM product_scans

        WHERE user_id = %s

        ORDER BY scan_date DESC

        """,

        (user_id,)

    )



    scans = cursor.fetchall()



    # -------------------------------------------------

    # NOTIFICATIONS

    # -------------------------------------------------



    cursor.execute(

        """

        SELECT

            id,

            user_id,

            title,

            message,

            is_read,

            created_at

        FROM notifications

        WHERE user_id = %s

        ORDER BY created_at DESC

        LIMIT 5

        """,

        (user_id,)

    )



    notifications = cursor.fetchall()



    # -------------------------------------------------

    # UNREAD NOTIFICATIONS

    # -------------------------------------------------



    cursor.execute(

        """

        SELECT COUNT(*) AS unread_count

        FROM notifications

        WHERE user_id = %s

        AND is_read = FALSE

        """,

        (user_id,)

    )



    notification_data = cursor.fetchone()



    unread_count = notification_data["unread_count"]



    cursor.close()



    # -------------------------------------------------

    # SCAN STATISTICS

    # -------------------------------------------------



    total_scans = len(scans)



    genuine_count = sum(

        1

        for scan in scans

        if str(scan.get("result", "")).lower() == "genuine"

    )



    fake_count = sum(

        1

        for scan in scans

        if str(scan.get("result", "")).lower() == "fake"

    )



    recent_count = sum(

        1

        for scan in scans

        if scan.get("scan_date")

        and scan["scan_date"].date() == date.today()

    )



    return render_template(

        "user_dashboard.html",

        name=session.get("user_name"),

        email=session.get("user_email"),

        scans=scans,

        total_scans=total_scans,

        genuine_count=genuine_count,

        fake_count=fake_count,

        recent_count=recent_count,

        notifications=notifications,

        unread_count=unread_count

    )





# =========================================================

# PROFILE

# =========================================================



@app.route("/profile", methods=["GET", "POST"])

def profile():



    if "user_id" not in session:

        return redirect("/login")



    user_id = session["user_id"]



    cursor = db.cursor(dictionary=True)



    if request.method == "POST":



        name = request.form.get("name", "").strip()

        phone = request.form.get("phone", "").strip()



        cursor.execute(

            """

            UPDATE users

            SET name = %s,

                phone = %s

            WHERE id = %s

            """,

            (name, phone, user_id)

        )



        db.commit()



        session["user_name"] = name



        cursor.close()



        return redirect("/profile")



    cursor.execute(

        """

        SELECT *

        FROM users

        WHERE id = %s

        """,

        (user_id,)

    )



    user = cursor.fetchone()



    cursor.execute(

        """

        SELECT *

        FROM product_scans

        WHERE user_id = %s

        ORDER BY scan_date DESC

        """,

        (user_id,)

    )



    scans = cursor.fetchall()



    cursor.close()



    total_scans = len(scans)



    genuine_count = sum(

        1

        for scan in scans

        if str(scan.get("result", "")).lower() == "genuine"

    )



    fake_count = sum(

        1

        for scan in scans

        if str(scan.get("result", "")).lower() == "fake"

    )



    return render_template(

        "profile.html",

        name=user["name"],

        email=user["email"],

        user_id=user["id"],

        phone=user.get("phone", ""),

        total_scans=total_scans,

        genuine_count=genuine_count,

        fake_count=fake_count

    )





# =========================================================

# PRODUCT SCAN

# =========================================================



@app.route("/product_scans", methods=["GET", "POST"])

def scan_product():



    if "user_id" not in session:

        return redirect("/login")



    user_id = session["user_id"]



    if request.method == "POST":



        product_name = request.form.get(

            "product_name",

            ""

        ).strip()



        brand = request.form.get(

            "brand",

            ""

        ).strip()



        barcode = request.form.get(

            "barcode",

            ""

        ).strip()



        category = request.form.get(

            "category",

            ""

        ).strip()



        if not product_name:

            return "Please enter product name."



        # -------------------------------------------------

        # IMAGE UPLOAD

        # -------------------------------------------------



        image = request.files.get("product_image")



        image_filename = None



        if image and image.filename:



            image_filename = secure_filename(

                image.filename

            )



            timestamp = datetime.now().strftime(

                "%Y%m%d%H%M%S%f"

            )



            image_filename = (

                timestamp + "_" + image_filename

            )



            image_path = os.path.join(

                app.config["UPLOAD_FOLDER"],

                image_filename

            )



            image.save(image_path)



        # -------------------------------------------------

        # SAVE SCAN

        # -------------------------------------------------



        cursor = db.cursor()



        cursor.execute(

            """

            INSERT INTO product_scans

            (

                user_id,

                product_name,

                brand,

                barcode,

                category,

                product_image,

                scan_type,

                result

            )

            VALUES

            (

                %s,

                %s,

                %s,

                %s,

                %s,

                %s,

                %s,

                %s

            )

            """,

            (

                user_id,

                product_name,

                brand,

                barcode,

                category,

                image_filename,

                "Product Scan",

                "Pending"

            )

        )



        scan_id = cursor.lastrowid



        # -------------------------------------------------

        # NOTIFICATION

        # -------------------------------------------------



        cursor.execute(

            """

            INSERT INTO notifications

            (

                user_id,

                title,

                message,

                is_read

            )

            VALUES

            (

                %s,

                %s,

                %s,

                0

            )

            """,

            (

                user_id,

                "Product Scan Submitted",

                f"{product_name} has been submitted for verification."

            )

        )



        db.commit()



        cursor.close()



        return redirect("/user_dashboard")



    # -------------------------------------------------

    # UNREAD NOTIFICATION COUNT

    # Required by product_scans.html for the notification badge.

    # -------------------------------------------------

    cursor = db.cursor(dictionary=True)

    cursor.execute(

        """

        SELECT COUNT(*) AS unread_count

        FROM notifications

        WHERE user_id = %s

          AND is_read = FALSE

        """,

        (user_id,)

    )

    notification_data = cursor.fetchone()

    unread_count = notification_data["unread_count"] if notification_data else 0

    cursor.close()



    return render_template(

        "product_scans.html",

        name=session.get("user_name"),

        email=session.get("user_email"),

        unread_count=unread_count

    )





# =========================================================

# SCAN HISTORY

# =========================================================



@app.route("/scan_history")

def scan_history():



    if "user_id" not in session:

        return redirect(url_for("login"))



    user_id = session["user_id"]



    cursor = db.cursor(dictionary=True)



    # -------------------------------------------------

    # SCAN HISTORY

    # -------------------------------------------------



    cursor.execute(

        """

        SELECT *

        FROM product_scans

        WHERE user_id = %s

        ORDER BY scan_date DESC

        """,

        (user_id,)

    )



    scans = cursor.fetchall()



    # -------------------------------------------------

    # REPORT HISTORY

    # -------------------------------------------------



    cursor.execute(

        """

        SELECT *

        FROM reports

        WHERE user_id = %s

        ORDER BY created_at DESC

        """,

        (user_id,)

    )



    reports = cursor.fetchall()



    cursor.close()



    return render_template(

        "scan_history.html",

        scans=scans,

        reports=reports,

        name=session.get("user_name", "User")

    )





# =========================================================

# VIEW SINGLE SCAN

# =========================================================



@app.route("/view_scan/<int:id>")

def view_scan(id):



    if "user_id" not in session:

        return redirect("/login")



    cursor = db.cursor(dictionary=True)



    cursor.execute(

        """

        SELECT *

        FROM product_scans

        WHERE id = %s

        AND user_id = %s

        """,

        (

            id,

            session["user_id"]

        )

    )



    scan = cursor.fetchone()



    cursor.close()



    if not scan:

        return "Scan not found."



    return render_template(

        "scan_details.html",

        scan=scan,

        name=session.get("user_name", "User")

    )





# =========================================================

# DELETE SCAN

# =========================================================



@app.route("/delete_scan/<int:id>")

def delete_scan(id):



    if "user_id" not in session:

        return redirect(url_for("login"))



    cursor = db.cursor(dictionary=True)



    cursor.execute(

        """

        SELECT product_image

        FROM product_scans

        WHERE id = %s

        AND user_id = %s

        """,

        (

            id,

            session["user_id"]

        )

    )



    scan = cursor.fetchone()



    cursor.execute(

        """

        DELETE FROM product_scans

        WHERE id = %s

        AND user_id = %s

        """,

        (

            id,

            session["user_id"]

        )

    )



    db.commit()



    cursor.close()



    # -------------------------------------------------

    # DELETE IMAGE

    # -------------------------------------------------



    if scan and scan.get("product_image"):



        image_path = os.path.join(

            app.config["UPLOAD_FOLDER"],

            scan["product_image"]

        )



        if os.path.exists(image_path):



            try:

                os.remove(image_path)

            except OSError:

                pass



    return redirect(url_for("scan_history"))





# =========================================================

# REPORT PRODUCT

# =========================================================



@app.route("/report_product", methods=["GET", "POST"])

def report_product():



    if "user_id" not in session:

        return redirect("/login")



    if request.method == "POST":



        product_name = request.form.get(

            "product_name",

            ""

        ).strip()



        brand = request.form.get(

            "brand",

            ""

        ).strip()



        reason = request.form.get(

            "reason",

            ""

        ).strip()



        description = request.form.get(

            "description",

            ""

        ).strip()



        user_id = session["user_id"]



        cursor = db.cursor()



        # -------------------------------------------------

        # SAVE REPORT

        # -------------------------------------------------



        cursor.execute(

            """

            INSERT INTO reports

            (

                user_id,

                product_name,

                brand,

                reason,

                description,

                status

            )

            VALUES

            (

                %s,

                %s,

                %s,

                %s,

                %s,

                %s

            )

            """,

            (

                user_id,

                product_name,

                brand,

                reason,

                description,

                "Pending"

            )

        )



        # -------------------------------------------------

        # NOTIFICATION

        # -------------------------------------------------



        cursor.execute(

            """

            INSERT INTO notifications

            (

                user_id,

                title,

                message,

                is_read

            )

            VALUES

            (

                %s,

                %s,

                %s,

                0

            )

            """,

            (

                user_id,

                "Product Report Submitted",

                f"Your report for {product_name} has been submitted successfully."

            )

        )



        db.commit()



        cursor.close()



        return redirect("/scan_history")



    return render_template(

        "report_product.html",

        name=session.get("user_name")

    )





# =========================================================

# ABOUT US

# =========================================================



@app.route("/about_us")

def about():



    if "user_id" not in session:

        return redirect("/login")



    return render_template(

        "about_us.html",

        name=session.get("user_name")

    )





# =========================================================

# CONTACT US

# =========================================================



@app.route("/contact", methods=["GET", "POST"])

def contact_us():



    if "user_id" not in session:

        return redirect("/login")



    user_id = session["user_id"]



    # -------------------------------------------------

    # SEND MESSAGE

    # -------------------------------------------------



    if request.method == "POST":



        name = request.form.get(

            "name",

            ""

        ).strip()



        email = request.form.get(

            "email",

            ""

        ).strip()



        subject = request.form.get(

            "subject",

            ""

        ).strip()



        message = request.form.get(

            "message",

            ""

        ).strip()



        if not name or not email or not subject or not message:

            return "Please fill all fields."



        cursor = db.cursor()



        # -------------------------------------------------

        # SAVE MESSAGE

        # -------------------------------------------------



        cursor.execute(

            """

            INSERT INTO contact_messages

            (

                user_id,

                name,

                email,

                subject,

                message,

                msg_status

            )

            VALUES

            (

                %s,

                %s,

                %s,

                %s,

                %s,

                %s

            )

            """,

            (

                user_id,

                name,

                email,

                subject,

                message,

                "Pending"

            )

        )



        # -------------------------------------------------

        # NOTIFICATION

        # -------------------------------------------------



        cursor.execute(

            """

            INSERT INTO notifications

            (

                user_id,

                title,

                message,

                is_read

            )

            VALUES

            (

                %s,

                %s,

                %s,

                0

            )

            """,

            (

                user_id,

                "Message Sent",

                f"Your message regarding '{subject}' has been sent successfully."

            )

        )



        db.commit()



        cursor.close()



        return redirect("/contact?sent=1")



    # -------------------------------------------------

    # MESSAGE HISTORY

    # -------------------------------------------------



    cursor = db.cursor(dictionary=True)



    cursor.execute(

        """

        SELECT

            id,

            name,

            email,

            subject,

            message,

            msg_status,

            admin_reply,

            replied_at,

            created_at

        FROM contact_messages

        WHERE user_id = %s

        ORDER BY created_at DESC

        """,

        (user_id,)

    )



    messages = cursor.fetchall()



    cursor.close()



    return render_template(

        "contact.html",

        name=session.get("user_name"),

        email=session.get("user_email"),

        messages=messages,

        success=(request.args.get("sent") == "1")

    )





# =========================================================

# DELETE CONTACT MESSAGE

# =========================================================



@app.route("/delete_message/<int:message_id>", methods=["POST"])

def delete_message(message_id):



    if "user_id" not in session:

        return redirect("/login")



    user_id = session["user_id"]



    cursor = db.cursor()



    cursor.execute(

        """

        DELETE FROM contact_messages

        WHERE id = %s

        AND user_id = %s

        """,

        (

            message_id,

            user_id

        )

    )



    db.commit()



    cursor.close()



    return redirect("/contact")





# =========================================================

# NOTIFICATIONS PAGE

# =========================================================



@app.route("/notifications")

def notifications():



    if "user_id" not in session:

        return redirect("/login")



    user_id = session["user_id"]



    cursor = db.cursor(dictionary=True)



    # -------------------------------------------------

    # ALL NOTIFICATIONS

    # -------------------------------------------------



    cursor.execute(

        """

        SELECT

            id,

            user_id,

            title,

            message,

            is_read,

            created_at

        FROM notifications

        WHERE user_id = %s

        ORDER BY created_at DESC

        """,

        (user_id,)

    )



    notification_list = cursor.fetchall()



    # -------------------------------------------------

    # UNREAD COUNT

    # -------------------------------------------------



    cursor.execute(

        """

        SELECT COUNT(*) AS unread_count

        FROM notifications

        WHERE user_id = %s

        AND is_read = FALSE

        """,

        (user_id,)

    )



    notification_data = cursor.fetchone()



    unread_count = notification_data["unread_count"]



    cursor.close()



    return render_template(

        "notifications.html",

        notifications=notification_list,

        unread_count=unread_count,

        name=session.get("user_name")

    )





# =========================================================

# MARK NOTIFICATION AS READ

# =========================================================



@app.route("/notifications/read/<int:notification_id>", methods=["GET", "POST"])

def mark_notification_read(notification_id):



    if "user_id" not in session:

        return redirect("/login")



    user_id = session["user_id"]



    cursor = db.cursor()



    cursor.execute(

        """

        UPDATE notifications

        SET is_read = TRUE

        WHERE id = %s

        AND user_id = %s

        """,

        (

            notification_id,

            user_id

        )

    )



    db.commit()



    cursor.close()



    if request.method == "POST":

        return "", 200



    return redirect("/notifications")





# =========================================================

# ADMIN DASHBOARD

# =========================================================



@app.route("/admin_dashboard")

def admin_dashboard():



    if session.get("admin_logged_in") is not True:

        return redirect("/login")



    cursor = db.cursor(dictionary=True)



    # TOTAL USERS



    cursor.execute(

        """

        SELECT COUNT(*) AS total_users

        FROM users

        """

    )



    total_users = cursor.fetchone()["total_users"]



    # TOTAL SCANS



    cursor.execute(

        """

        SELECT COUNT(*) AS total_scans

        FROM product_scans

        """

    )



    total_scans = cursor.fetchone()["total_scans"]



    # GENUINE



    cursor.execute(

        """

        SELECT COUNT(*) AS genuine_count

        FROM product_scans

        WHERE LOWER(result) = 'genuine'

        """

    )



    genuine_count = cursor.fetchone()["genuine_count"]



    # FAKE



    cursor.execute(

        """

        SELECT COUNT(*) AS fake_count

        FROM product_scans

        WHERE LOWER(result) = 'fake'

        """

    )



    fake_count = cursor.fetchone()["fake_count"]



    # PENDING



    cursor.execute(

        """

        SELECT COUNT(*) AS pending_count

        FROM product_scans

        WHERE LOWER(result) = 'pending'

        """

    )



    pending_count = cursor.fetchone()["pending_count"]



    # TOTAL REPORTS



    cursor.execute(

        """

        SELECT COUNT(*) AS total_reports

        FROM reports

        """

    )



    total_reports = cursor.fetchone()["total_reports"]



    # RECENT SCANS



    cursor.execute(

        """

        SELECT

            ps.*,

            u.name AS user_name,

            u.email AS user_email

        FROM product_scans ps

        LEFT JOIN users u

            ON ps.user_id = u.id

        ORDER BY ps.scan_date DESC

        LIMIT 10

        """

    )



    recent_scans = cursor.fetchall()



    # RECENT REPORTS



    cursor.execute(

        """

        SELECT

            r.*,

            u.name AS user_name,

            u.email AS user_email

        FROM reports r

        LEFT JOIN users u

            ON r.user_id = u.id

        ORDER BY r.created_at DESC

        LIMIT 10

        """

    )



    recent_reports = cursor.fetchall()



    cursor.close()



    return render_template(

        "admin_dashboard.html",

        admin_name=session.get(

            "admin_name",

            "Admin"

        ),

        admin_email=session.get(

            "admin_email",

            ADMIN_EMAIL

        ),

        total_users=total_users,

        total_scans=total_scans,

        genuine_count=genuine_count,

        fake_count=fake_count,

        pending_count=pending_count,

        total_reports=total_reports,

        recent_scans=recent_scans,

        recent_reports=recent_reports

    )





# =========================================================

# ADMIN LOGOUT

# =========================================================



@app.route("/admin_logout")

def admin_logout():



    session.clear()



    return redirect("/login")





# =========================================================

# GENERAL LOGOUT

# =========================================================



@app.route("/logout")

def logout():



    session.clear()



    return redirect("/login")





# =========================================================

# MANAGE USERS

# =========================================================



@app.route("/manage_users")

def manage_users():



    if session.get("admin_logged_in") is not True:

        return redirect("/login")



    cursor = db.cursor(dictionary=True)



    cursor.execute(

        """

        SELECT *

        FROM users

        ORDER BY id DESC

        """

    )



    users = cursor.fetchall()



    cursor.close()



    return render_template(

        "manage_users.html",

        users=users,

        admin_name=session.get(

            "admin_name",

            "Admin"

        ),

        admin_email=session.get(

            "admin_email",

            ADMIN_EMAIL

        )

    )





# =========================================================

# DELETE USER

# =========================================================



@app.route("/admin/delete_user/<int:user_id>")

def delete_user(user_id):



    if session.get("admin_logged_in") is not True:

        return redirect("/login")



    cursor = db.cursor()



    cursor.execute(

        """

        DELETE FROM users

        WHERE id = %s

        """,

        (user_id,)

    )



    db.commit()



    cursor.close()



    return redirect("/manage_users")





# =========================================================

# ADMIN PRODUCT SCANS

# =========================================================



@app.route("/admin_product_scans")

def admin_product_scans():



    if session.get("admin_logged_in") is not True:

        return redirect("/login")



    cursor = db.cursor(dictionary=True)



    cursor.execute(

        """

        SELECT

            ps.*,

            u.name AS user_name,

            u.email AS user_email

        FROM product_scans ps

        LEFT JOIN users u

            ON ps.user_id = u.id

        ORDER BY ps.scan_date DESC

        """

    )



    scans = cursor.fetchall()



    cursor.close()



    total_scans = len(scans)



    genuine_count = sum(

        1

        for scan in scans

        if str(scan.get("result", "")).lower() == "genuine"

    )



    fake_count = sum(

        1

        for scan in scans

        if str(scan.get("result", "")).lower() == "fake"

    )



    pending_count = sum(

        1

        for scan in scans

        if str(scan.get("result", "")).lower() == "pending"

    )



    return render_template(

        "admin_product_scans.html",

        admin_name=session.get(

            "admin_name",

            "Admin"

        ),

        admin_email=session.get(

            "admin_email",

            ADMIN_EMAIL

        ),

        scans=scans,

        total_scans=total_scans,

        genuine_count=genuine_count,

        fake_count=fake_count,

        pending_count=pending_count

    )





# =========================================================

# ADMIN UPDATE PRODUCT SCAN RESULT

# =========================================================



@app.route(

    "/admin/update_scan/<int:scan_id>",

    methods=["POST"]

)

def update_scan_result(scan_id):



    if session.get("admin_logged_in") is not True:

        return redirect("/login")



    result = request.form.get(

        "result",

        "Pending"

    ).strip()



    allowed_results = [

        "Pending",

        "Genuine",

        "Fake"

    ]



    if result not in allowed_results:

        return "Invalid scan result."



    cursor = db.cursor(dictionary=True)



    # -------------------------------------------------

    # GET OLD RESULT

    # -------------------------------------------------



    cursor.execute(

        """

        SELECT

            user_id,

            product_name,

            result

        FROM product_scans

        WHERE id = %s

        """,

        (scan_id,)

    )



    scan_data = cursor.fetchone()



    if not scan_data:



        cursor.close()



        return "Scan not found."



    user_id = scan_data["user_id"]

    product_name = scan_data["product_name"]

    old_result = scan_data["result"]



    # -------------------------------------------------

    # UPDATE RESULT

    # -------------------------------------------------



    cursor.execute(

        """

        UPDATE product_scans

        SET result = %s

        WHERE id = %s

        """,

        (

            result,

            scan_id

        )

    )



    # -------------------------------------------------

    # USER NOTIFICATION

    # -------------------------------------------------



    if result in ["Genuine", "Fake"] and old_result != result:



        if result == "Genuine":



            title = "Product Verification Complete"



            message = (

                f"The verification result for {product_name} "

                f"is Genuine."

            )



        else:



            title = "Product Verification Complete"



            message = (

                f"The verification result for {product_name} "

                f"is Fake."

            )



        cursor.execute(

            """

            INSERT INTO notifications

            (

                user_id,

                title,

                message,

                is_read

            )

            VALUES

            (

                %s,

                %s,

                %s,

                0

            )

            """,

            (

                user_id,

                title,

                message

            )

        )



    db.commit()



    cursor.close()



    return redirect("/admin_product_scans")





# =========================================================

# ADMIN REPORTS

# =========================================================



@app.route("/admin_reports")

def admin_reports():



    if session.get("admin_logged_in") is not True:

        return redirect("/login")



    cursor = db.cursor(dictionary=True)



    cursor.execute(

        """

        SELECT

            r.*,

            u.name AS user_name,

            u.email AS user_email

        FROM reports r

        LEFT JOIN users u

            ON r.user_id = u.id

        ORDER BY r.created_at DESC

        """

    )



    reports = cursor.fetchall()



    total_reports = len(reports)



    pending_reports = sum(

        1

        for r in reports

        if str(

            r.get("status", "Pending")

        ).lower() == "pending"

    )



    resolved_reports = sum(

        1

        for r in reports

        if str(

            r.get("status", "")

        ).lower() == "resolved"

    )



    cursor.close()



    return render_template(

        "admin_reports.html",

        reports=reports,

        total_reports=total_reports,

        pending_reports=pending_reports,

        resolved_reports=resolved_reports,

        admin_name=session.get(

            "admin_name",

            "Admin"

        )

    )





# =========================================================

# ADMIN UPDATE REPORT

# =========================================================



@app.route(

    "/admin/update_report/<int:report_id>",

    methods=["POST"]

)

def update_report(report_id):



    if session.get("admin_logged_in") is not True:

        return redirect("/login")



    status = request.form.get(

        "status",

        "Pending"

    ).strip()



    admin_action = request.form.get(

        "admin_action",

        ""

    ).strip()



    allowed_statuses = [

        "Pending",

        "In Review",

        "Resolved",

        "Rejected"

    ]



    if status not in allowed_statuses:

        return "Invalid report status."



    cursor = db.cursor(dictionary=True)



    # -------------------------------------------------

    # GET EXISTING REPORT

    # -------------------------------------------------



    cursor.execute(

        """

        SELECT

            user_id,

            product_name,

            status,

            admin_action

        FROM reports

        WHERE id = %s

        """,

        (report_id,)

    )



    report_data = cursor.fetchone()



    if not report_data:



        cursor.close()



        return "Report not found."



    user_id = report_data["user_id"]

    product_name = report_data["product_name"]



    old_status = report_data["status"]

    old_action = report_data["admin_action"] or ""



    status_changed = old_status != status

    action_changed = old_action != admin_action



    # -------------------------------------------------

    # UPDATE REPORT

    # -------------------------------------------------



    cursor.execute(

        """

        UPDATE reports

        SET

            status = %s,

            admin_action = %s,

            action_date = %s

        WHERE id = %s

        """,

        (

            status,

            admin_action,

            datetime.now(),

            report_id

        )

    )



    # -------------------------------------------------

    # NOTIFICATION

    # -------------------------------------------------



    if status_changed or action_changed:



        if status == "In Review":



            title = "Report In Review"



            message = (

                f"Your report for {product_name} "

                f"is now being reviewed by the admin."

            )



        elif status == "Resolved":



            title = "Report Resolved"



            message = (

                f"Your report for {product_name} "

                f"has been resolved."

            )



            if admin_action:



                message += (

                    f" Admin response: {admin_action}"

                )



        elif status == "Rejected":



            title = "Report Update"



            message = (

                f"Your report for {product_name} "

                f"has been rejected."

            )



            if admin_action:



                message += (

                    f" Admin response: {admin_action}"

                )



        else:



            title = "Report Updated"



            message = (

                f"Your report for {product_name} "

                f"has been updated."

            )



        cursor.execute(

            """

            INSERT INTO notifications

            (

                user_id,

                title,

                message,

                is_read

            )

            VALUES

            (

                %s,

                %s,

                %s,

                0

            )

            """,

            (

                user_id,

                title,

                message

            )

        )



    db.commit()



    cursor.close()



    return redirect("/admin_reports")





# =========================================================

# ADMIN MESSAGES

# =========================================================



@app.route("/message")

def admin_messages():



    if session.get("admin_logged_in") is not True:

        return redirect("/login")



    cursor = db.cursor(dictionary=True)



    cursor.execute(

        """

        SELECT

            id,

            user_id,

            name,

            email,

            subject,

            message,

            msg_status,

            admin_reply,

            replied_at,

            created_at

        FROM contact_messages

        ORDER BY created_at DESC

        """

    )



    messages = cursor.fetchall()



    cursor.close()



    return render_template(

        "admin_messages.html",

        messages=messages,

        admin_name=session.get(

            "admin_name",

            "Admin"

        )

    )





# =========================================================

# ADMIN REPLY / UPDATE MESSAGE

# =========================================================



@app.route(

    "/admin/update_message/<int:message_id>",

    methods=["POST"]

)

def update_message(message_id):



    if session.get("admin_logged_in") is not True:

        return redirect("/login")



    status = request.form.get(

        "msg_status",

        "Pending"

    ).strip()



    admin_reply = request.form.get(

        "admin_reply",

        ""

    ).strip()



    allowed_statuses = [

        "Pending",

        "In Review",

        "Replied"

    ]



    if status not in allowed_statuses:

        return "Invalid message status."



    cursor = db.cursor(dictionary=True)



    # -------------------------------------------------

    # GET OLD MESSAGE

    # -------------------------------------------------



    cursor.execute(

        """

        SELECT

            user_id,

            subject,

            msg_status,

            admin_reply

        FROM contact_messages

        WHERE id = %s

        """,

        (message_id,)

    )



    message_data = cursor.fetchone()



    if not message_data:



        cursor.close()



        return "Message not found."



    user_id = message_data["user_id"]

    subject = message_data["subject"]



    old_status = message_data["msg_status"]

    old_reply = message_data["admin_reply"] or ""



    status_changed = old_status != status

    reply_changed = old_reply != admin_reply



    # -------------------------------------------------

    # REPLY DATE

    # -------------------------------------------------



    if status == "Replied" and admin_reply:



        replied_at = datetime.now()



    else:



        replied_at = None



    # -------------------------------------------------

    # UPDATE MESSAGE

    # -------------------------------------------------



    cursor.execute(

        """

        UPDATE contact_messages

        SET

            msg_status = %s,

            admin_reply = %s,

            replied_at = %s

        WHERE id = %s

        """,

        (

            status,

            admin_reply,

            replied_at,

            message_id

        )

    )



    # -------------------------------------------------

    # USER NOTIFICATION

    # -------------------------------------------------



    if status == "Replied" and admin_reply:



        if status_changed or reply_changed:



            cursor.execute(

                """

                INSERT INTO notifications

                (

                    user_id,

                    title,

                    message,

                    is_read

                )

                VALUES

                (

                    %s,

                    %s,

                    %s,

                    0

                )

                """,

                (

                    user_id,

                    "Admin Replied",

                    f"Admin has replied to your message regarding '{subject}'."

                )

            )



    elif status == "In Review":



        if status_changed:



            cursor.execute(

                """

                INSERT INTO notifications

                (

                    user_id,

                    title,

                    message,

                    is_read

                )

                VALUES

                (

                    %s,

                    %s,

                    %s,

                    0

                )

                """,

                (

                    user_id,

                    "Message In Review",

                    f"Your message regarding '{subject}' is now being reviewed."

                )

            )



    db.commit()



    cursor.close()



    return redirect("/message")





# =========================================================

# VERIFY PRODUCT

# =========================================================



@app.route("/verify_product", methods=["POST"])
def verify_product():
    print("VERIFY REQUEST RECEIVED", datetime.now(), flush=True)
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    product_name = request.form.get("product_name", "").strip()
    brand = request.form.get("brand", "").strip()
    barcode = request.form.get("barcode", "").strip()
    category = request.form.get("category", "").strip()
    image = request.files.get("product_image")

    if not product_name:
        return "Please enter product name.", 400

    if not image or not image.filename:
        return "Please upload a product image.", 400

    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    original_name = secure_filename(image.filename)
    extension = os.path.splitext(original_name)[1].lower()

    if not original_name or extension not in allowed_extensions:
        return "Please upload a JPG, JPEG, PNG, or WEBP image.", 400

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    image_filename = f"{timestamp}_{original_name}"
    image_path = os.path.join(app.config["UPLOAD_FOLDER"], image_filename)
    image.save(image_path)
    print("VERIFY ROUTE REACHED AI CHECK", flush=True)
    print("PRODUCT:", product_name, "| USER:", user_id, flush=True)
    # Use the real Nyckel prediction; never assume a product is genuine.
    try:
        ml_result = predict_product(image_path)

        ai_label = ml_result["prediction"].lower()
        confidence = ml_result["confidence"]

        if ai_label == "genuine":
            result = "Genuine"
        elif ai_label == "fake":
            result = "Fake"
        else:
            result = "Pending"

    except (ValueError, KeyError, TypeError, OSError) as error:
        app.logger.exception("ML model prediction failed")
        return f"ML model error: {error!s}", 500

    cursor = None
    try:
        db.ping(reconnect=True, attempts=3, delay=1)
        cursor = db.cursor()

        cursor.execute(
            """
            INSERT INTO product_scans
                (user_id, product_name, brand, barcode, category,
                 product_image, scan_type, result)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                product_name,
                brand,
                barcode,
                category,
                image_filename,
                "Product Verification",
                result,
            ),
        )

        if result == "Pending":
            notification_message = (
                f"AI returned the label '{ai_label}' for {product_name}. "
                "Please review the prediction manually."
            )
        else:
            notification_message = (
                f"AI prediction for {product_name}: {result} "
                f"({confidence}% confidence). This is not proof of authenticity."
            )

        cursor.execute(
            """
            INSERT INTO notifications (user_id, title, message, is_read)
            VALUES (%s, %s, %s, 0)
            """,
            (user_id, "Product Verification Complete", notification_message),
        )
        db.commit()

    except mysql.connector.Error:
        db.rollback()
        app.logger.exception("Could not save the AI verification to MySQL")
        return "AI prediction received, but saving the result to MySQL failed.", 500
    finally:
        if cursor is not None:
            cursor.close()

    return render_template(
        "verification_result.html",
        product_name=product_name,
        brand=brand,
        barcode=barcode,
        category=category,
        result=result,
        confidence=confidence,
        image=image_filename,
    )


if __name__ == "__main__":



    app.run(debug=True)