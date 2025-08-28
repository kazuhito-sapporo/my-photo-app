import streamlit as st
import cv2
import numpy as np
from PIL import Image
import os
import sqlite3
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from openai import OpenAI
import base64
from io import BytesIO
import datetime

# === Streamlit Secrets から API キー取得 ===
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
client = OpenAI(api_key=OPENAI_API_KEY)

# === DB初期化 ===
def init_db():
    conn = sqlite3.connect("photo_comments.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            composition TEXT,
            brightness TEXT,
            sharpness TEXT,
            gpt_comment TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# === DB保存 ===
def save_to_db(filename, comp, bright, sharp, gpt_comment):
    conn = sqlite3.connect("photo_comments.db")
    c = conn.cursor()
    c.execute('''
        INSERT INTO comments (filename, composition, brightness, sharpness, gpt_comment)
        VALUES (?, ?, ?, ?, ?)
    ''', (filename, comp, bright, sharp, gpt_comment))
    conn.commit()
    conn.close()

# === 評価関数 ===
def evaluate_brightness(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    avg = np.mean(gray)
    if avg > 180:
        return "この写真は明るめです。"
    elif avg < 70:
        return "この写真は暗めです。"
    else:
        return "この写真は適度な明るさです。"

def evaluate_sharpness(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    var = lap.var()
    if var < 100:
        return f"シャープさがやや足りません（ピントが甘い可能性）[分散={var:.2f}]"
    else:
        return f"シャープな印象です [分散={var:.2f}]"

def evaluate_composition(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    m = cv2.moments(gray)
    if m["m00"] != 0:
        cx = int(m["m10"] / m["m00"])
        cy = int(m["m01"] / m["m00"])
        h, w = gray.shape
        dx = abs(cx - w // 2) / w
        dy = abs(cy - h // 2) / h
        if dx < 0.1 and dy < 0.1:
            return "被写体が中央にあり、安定した構図です。"
        else:
            return "被写体が中心からずれていて、動きやバランスを感じます。"
    else:
