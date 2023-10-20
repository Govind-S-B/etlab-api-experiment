from flask import Blueprint, jsonify, request
import requests
from config import Config
from bs4 import BeautifulSoup
from app.utils.cookie_required import require_cookie_auth
from flasgger import swag_from
from app.docs.swagger import swagger_present_spec

bp = Blueprint("present", __name__, url_prefix="/api")


@bp.route("/present", methods=["GET"])
@require_cookie_auth
@swag_from(swagger_present_spec)
def present():
    try:
        month = int(request.args.get("month"))
        semester = int(request.args.get("semester"))
        year = int(request.args.get("year"))
    except (ValueError, TypeError):
        return jsonify({"message": "Invalid parameters"}), 400

    if not (month >= 1 and month <= 12):
        return jsonify({"message": "Invalid month"}), 400

    if not (semester >= 1 and semester <= 8):
        return jsonify({"message": "Invalid semester"}), 400

    headers = {
        "User-Agent": Config.USER_AGENT,
    }

    cookie = {"RITSESSIONID": request.headers["Cookie"]}
    payload = {
        "month": month,
        "semester": (8 + semester),
        "year": year,
    }
    response = requests.post(
        f"{Config.BASE_URL}/ktuacademics/student/attendance",
        headers=headers,
        cookies=cookie,
        data=payload,
    )
    if response.status_code != 200:
        return jsonify({"message": "Failed to fetch data"}), 500

    soup = BeautifulSoup(response.text, "html.parser")
    if "login" in soup.title.string.lower():
        return jsonify({"message": "Cookie expired. Please login again."}), 401

    try:
        semester_element = soup.find("select", {"name": "semester"}).find(
            "option", {"selected": "selected"}
        )
        semester = semester_element.get_text(strip=True).lower()
        semester_num = semester_element["value"]

        month_element = soup.find("select", {"name": "month"}).find(
            "option", {"selected": "selected"}
        )
        month = month_element.get_text(strip=True).lower()
        month_num = month_element["value"]
        year = (
            soup.find("select", {"name": "year"})
            .find("option", {"selected": "selected"})
            .text
        ).strip()

        present_hours_data = []

        table = soup.find("table", {"id": "itsthetable"})

        rows = table.select("tbody tr")
        for row in rows:
            day = row.find("th").text.strip()
            cols = row.find_all("td")

            if len(cols) == 1:
                continue

            for hour, col in enumerate(cols, start=1):
                if "present" in col.get("class"):
                    present_hour_data = {}
                    suffixes = ["st", "nd", "rd", "th"]
                    if day.endswith(tuple(suffixes)):
                        day = day[:-2]
                    present_hour_data["day"] = int(day)
                    present_hour_data["hour"] = hour
                    present_hour_data["subject_code"] = col.text.split("-")[0].strip()
                    present_hour_data["subject_name"] = (
                        col.text.split("-")[1].strip().split("\n")[0].strip()
                    )
                    present_hours_data.append(present_hour_data)

        respone_dict = {
            "month": month,
            "month_num": month_num,
            "semester": semester,
            "semester_num": semester_num,
            "year": year,
            "present_hours": present_hours_data,
        }
        return (
            jsonify({"message": "Successfully fetched data", "data": respone_dict}),
            200,
        )
    except Exception as e:
        print(e)
        return jsonify({"message": "Failed to parse data"}), 500
