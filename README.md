# 💰 CashControl — Telegram Finance Bot

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python"/>
  <img src="https://img.shields.io/badge/Aiogram-Async-green?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Status-Production%20Ready-black?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Architecture-FSM-orange?style=for-the-badge"/>
</p>

<p align="center">
  <b>Production-style Telegram bot for personal finance management</b><br/>
  Multi-currency • Real-time exchange • Async architecture
</p>

---

## 🚀 Overview

**CashControl** is a production-style Telegram bot designed for real-world personal finance management.

This is **NOT a demo project** — it simulates real backend behavior:
- state-driven user interaction
- external API integration
- multi-currency accounting
- production deployment mindset

---

## ⚙️ Features

| Feature | Description |
|--------|------------|
| ➕ Income | Add income with validation |
| ➖ Expense | Track categorized expenses |
| 💼 Balance | Multi-currency balance |
| 📜 History | Full transaction log |
| 🔄 Exchange | Real exchange with confirmation |
| 🧮 Calculator | Exchange without saving |
| ❌ Validation | No crashes on bad input |

---

## 🧠 Tech Stack

- **Python (Async)**
- **Aiogram (Telegram framework)**
- **FSM (Finite State Machine)**
- **aiohttp (external API calls)**
- **ExchangeRate API**
- **systemd (24/7 runtime)**

---

## 🧩 Architecture

### 🔷 System Overview

```mermaid
flowchart TD
    User[Telegram User] --> Bot[Telegram Bot]
    Bot --> FSM[FSM State Manager]
    FSM --> Logic[Business Logic Layer]

    Logic --> Balance[Balance Engine]
    Logic --> Exchange[Exchange Service]
    Logic --> Storage[Transaction Storage]

    Exchange --> API[Exchange API]
    API --> Exchange
