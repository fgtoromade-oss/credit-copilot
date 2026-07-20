import os
import json
import uuid
import datetime
from flask import Flask, render_template_string, request, jsonify, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename
import sqlite3

# Optional: Gemini AI integration (free tier available)
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "credit_copilot_dev_key_2026")
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs("data", exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx", "csv", "txt", "png", "jpg", "jpeg"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    conn = sqlite3.connect("data/credit_copilot.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deals (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, industry TEXT,
            loan_amount REAL, loan_purpose TEXT, status TEXT DEFAULT "active",
            created_at TEXT, updated_at TEXT, business_overview TEXT,
            initial_risks TEXT, missing_info TEXT, memo_content TEXT,
            facility_amount REAL, facility_tenor TEXT, facility_repayment TEXT,
            facility_conditions TEXT, facility_covenants TEXT, facility_collateral TEXT,
            facility_justification TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meetings (
            id TEXT PRIMARY KEY, deal_id TEXT, transcript TEXT, notes TEXT,
            summary TEXT, created_at TEXT, FOREIGN KEY (deal_id) REFERENCES deals (id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY, deal_id TEXT, filename TEXT, filepath TEXT,
            doc_type TEXT, uploaded_at TEXT, FOREIGN KEY (deal_id) REFERENCES deals (id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS financial_analysis (
            id TEXT PRIMARY KEY, deal_id TEXT, analysis_type TEXT, data TEXT,
            created_at TEXT, FOREIGN KEY (deal_id) REFERENCES deals (id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS credit_reviews (
            id TEXT PRIMARY KEY, deal_id TEXT, question TEXT, response TEXT,
            status TEXT DEFAULT "pending", created_at TEXT, FOREIGN KEY (deal_id) REFERENCES deals (id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id TEXT PRIMARY KEY, deal_id TEXT, role TEXT, content TEXT,
            created_at TEXT, FOREIGN KEY (deal_id) REFERENCES deals (id)
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_gemini_response(prompt, context=""):
    if not GEMINI_AVAILABLE:
        return None
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-3-flash-preview")
        full_prompt = "You are Credit Copilot, an expert commercial banking assistant. "
        full_prompt += "You help relationship managers analyze deals, write credit memos, and respond to credit review questions. "
        full_prompt += "Be professional, concise, and use banking terminology appropriately.\n\n"
        full_prompt += "Context about this deal: " + context + "\n\n"
        full_prompt += "User request: " + prompt
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return "[AI temporarily unavailable. Error: " + str(e) + "]"

BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Credit Copilot{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #1a365d;
            --primary-light: #2c5282;
            --accent: #c53030;
            --accent-light: #e53e3e;
            --success: #276749;
            --warning: #c05621;
            --bg: #f7fafc;
            --card-bg: #ffffff;
            --text: #1a202c;
            --text-muted: #718096;
            --border: #e2e8f0;
        }

        * { font-family: 'Inter', sans-serif; }

        body {
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
        }

        .navbar {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
            box-shadow: 0 4px 20px rgba(26, 54, 93, 0.3);
            padding: 1rem 0;
        }

        .navbar-brand {
            font-weight: 700;
            font-size: 1.5rem;
            color: white !important;
            letter-spacing: -0.5px;
        }

        .navbar-brand i { margin-right: 0.5rem; }

        .nav-link { color: rgba(255,255,255,0.85) !important; font-weight: 500; }
        .nav-link:hover { color: white !important; }

        .card {
            border: none;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            transition: all 0.3s ease;
            background: var(--card-bg);
        }

        .card:hover {
            box-shadow: 0 8px 25px rgba(0,0,0,0.12);
            transform: translateY(-2px);
        }

        .card-header {
            background: transparent;
            border-bottom: 1px solid var(--border);
            padding: 1.25rem;
            font-weight: 600;
            font-size: 0.95rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--primary);
        }

        .btn-primary {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
            border: none;
            border-radius: 8px;
            padding: 0.6rem 1.5rem;
            font-weight: 500;
        }

        .btn-primary:hover {
            background: linear-gradient(135deg, var(--primary-light) 0%, var(--primary) 100%);
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(26, 54, 93, 0.3);
        }

        .btn-accent {
            background: linear-gradient(135deg, var(--accent) 0%, var(--accent-light) 100%);
            border: none;
            color: white;
            border-radius: 8px;
        }

        .btn-accent:hover {
            background: linear-gradient(135deg, var(--accent-light) 0%, var(--accent) 100%);
            color: white;
        }

        .btn-outline-primary {
            border: 2px solid var(--primary);
            color: var(--primary);
            border-radius: 8px;
            font-weight: 500;
        }

        .btn-outline-primary:hover {
            background: var(--primary);
            color: white;
        }

        .form-control, .form-select {
            border: 2px solid var(--border);
            border-radius: 8px;
            padding: 0.75rem 1rem;
            font-size: 0.95rem;
            transition: all 0.2s;
        }

        .form-control:focus, .form-select:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(26, 54, 93, 0.1);
        }

        .deal-card {
            border-left: 4px solid var(--primary);
            padding: 1.5rem;
        }

        .deal-card.active { border-left-color: var(--success); }
        .deal-card.pending { border-left-color: var(--warning); }
        .deal-card.review { border-left-color: var(--accent); }

        .stat-card {
            text-align: center;
            padding: 1.5rem;
        }

        .stat-number {
            font-size: 2rem;
            font-weight: 700;
            color: var(--primary);
        }

        .stat-label {
            font-size: 0.85rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .section-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--primary);
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .chat-container {
            height: 400px;
            overflow-y: auto;
            background: #f8f9fa;
            border-radius: 12px;
            padding: 1rem;
        }

        .chat-message {
            margin-bottom: 1rem;
            max-width: 85%;
        }

        .chat-message.user {
            margin-left: auto;
            text-align: right;
        }

        .chat-message.user .message-bubble {
            background: var(--primary);
            color: white;
            border-radius: 12px 12px 2px 12px;
        }

        .chat-message.assistant .message-bubble {
            background: white;
            color: var(--text);
            border: 1px solid var(--border);
            border-radius: 12px 12px 12px 2px;
        }

        .message-bubble {
            padding: 0.75rem 1rem;
            display: inline-block;
            max-width: 100%;
            word-wrap: break-word;
        }

        .message-time {
            font-size: 0.7rem;
            color: var(--text-muted);
            margin-top: 0.25rem;
        }

        .tab-content {
            padding: 1.5rem 0;
        }

        .nav-tabs .nav-link {
            border: none;
            color: var(--text-muted);
            font-weight: 500;
            padding: 0.75rem 1.25rem;
            border-bottom: 3px solid transparent;
        }

        .nav-tabs .nav-link.active {
            color: var(--primary);
            border-bottom-color: var(--primary);
            background: transparent;
        }

        .document-item {
            display: flex;
            align-items: center;
            padding: 0.75rem;
            background: #f8f9fa;
            border-radius: 8px;
            margin-bottom: 0.5rem;
        }

        .document-item i {
            font-size: 1.5rem;
            margin-right: 0.75rem;
            color: var(--primary);
        }

        .flash-messages {
            position: fixed;
            top: 80px;
            right: 20px;
            z-index: 1050;
            max-width: 400px;
        }

        .alert {
            border-radius: 8px;
            border: none;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }

        .ratio-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 1rem;
        }

        .ratio-item {
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 8px;
            text-align: center;
        }

        .ratio-value {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--primary);
        }

        .ratio-label {
            font-size: 0.8rem;
            color: var(--text-muted);
        }

        .memo-editor {
            min-height: 500px;
            font-family: 'Courier New', monospace;
            font-size: 0.9rem;
            line-height: 1.6;
        }

        .progress-tracker {
            display: flex;
            justify-content: space-between;
            margin-bottom: 2rem;
            position: relative;
        }

        .progress-tracker::before {
            content: '';
            position: absolute;
            top: 15px;
            left: 0;
            right: 0;
            height: 3px;
            background: var(--border);
            z-index: 0;
        }

        .progress-step {
            position: relative;
            z-index: 1;
            text-align: center;
            flex: 1;
        }

        .progress-step .step-circle {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background: var(--border);
            color: var(--text-muted);
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 0.5rem;
            font-weight: 600;
            font-size: 0.85rem;
        }

        .progress-step.completed .step-circle {
            background: var(--success);
            color: white;
        }

        .progress-step.active .step-circle {
            background: var(--primary);
            color: white;
        }

        .progress-step .step-label {
            font-size: 0.75rem;
            color: var(--text-muted);
            font-weight: 500;
        }

        .progress-step.completed .step-label,
        .progress-step.active .step-label {
            color: var(--text);
        }

        .ai-badge {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-size: 0.7rem;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .floating-action-btn {
            position: fixed;
            bottom: 30px;
            right: 30px;
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--accent) 0%, var(--accent-light) 100%);
            color: white;
            border: none;
            box-shadow: 0 4px 15px rgba(197, 48, 48, 0.4);
            font-size: 1.5rem;
            z-index: 1000;
            transition: all 0.3s;
        }

        .floating-action-btn:hover {
            transform: scale(1.1);
            box-shadow: 0 6px 20px rgba(197, 48, 48, 0.5);
        }

        .empty-state {
            text-align: center;
            padding: 3rem;
            color: var(--text-muted);
        }

        .empty-state i {
            font-size: 3rem;
            margin-bottom: 1rem;
            opacity: 0.5;
        }

        @media (max-width: 768px) {
            .progress-tracker { display: none; }
            .stat-number { font-size: 1.5rem; }
        }
    </style>
    {% block extra_css %}{% endblock %}
</head>
<body>
    <nav class="navbar navbar-expand-lg">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('index') }}">
                <i class="bi bi-shield-check"></i> Credit Copilot
            </a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon" style="filter: invert(1);"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav ms-auto">
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('index') }}">
                            <i class="bi bi-grid"></i> Dashboard
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('new_deal') }}">
                            <i class="bi bi-plus-circle"></i> New Deal
                        </a>
                    </li>
                </ul>
            </div>
        </div>
    </nav>

    <div class="flash-messages">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ 'danger' if category == 'error' else category }} alert-dismissible fade show" role="alert">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
    </div>

    <main class="container py-4">
        {% block content %}{% endblock %}
    </main>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Auto-dismiss flash messages
        setTimeout(() => {
            document.querySelectorAll('.alert').forEach(alert => {
                alert.classList.remove('show');
                setTimeout(() => alert.remove(), 300);
            });
        }, 5000);
    </script>
    {% block extra_js %}{% endblock %}
</body>
</html>

"""

INDEX_TEMPLATE = """
{% extends "base.html" %}

{% block title %}Dashboard - Credit Copilot{% endblock %}

{% block content %}
<div class="row mb-4">
    <div class="col-12">
        <div class="d-flex justify-content-between align-items-center">
            <div>
                <h2 class="mb-1">Credit Copilot Dashboard</h2>
                <p class="text-muted mb-0">Your AI-powered commercial lending assistant</p>
            </div>
            <a href="{{ url_for('new_deal') }}" class="btn btn-primary btn-lg">
                <i class="bi bi-plus-lg"></i> Create New Deal
            </a>
        </div>
    </div>
</div>

<!-- Stats Row -->
<div class="row mb-4">
    <div class="col-md-3 col-sm-6 mb-3">
        <div class="card stat-card">
            <div class="stat-number">{{ deals|length }}</div>
            <div class="stat-label">Total Deals</div>
        </div>
    </div>
    <div class="col-md-3 col-sm-6 mb-3">
        <div class="card stat-card">
            <div class="stat-number text-success">{{ deals|selectattr('status', 'equalto', 'active')|list|length }}</div>
            <div class="stat-label">Active</div>
        </div>
    </div>
    <div class="col-md-3 col-sm-6 mb-3">
        <div class="card stat-card">
            <div class="stat-number text-warning">{{ deals|selectattr('status', 'equalto', 'pending')|list|length }}</div>
            <div class="stat-label">Pending Review</div>
        </div>
    </div>
    <div class="col-md-3 col-sm-6 mb-3">
        <div class="card stat-card">
            <div class="stat-number text-danger">{{ deals|selectattr('status', 'equalto', 'review')|list|length }}</div>
            <div class="stat-label">In Review</div>
        </div>
    </div>
</div>

<!-- Deals Grid -->
<div class="row">
    <div class="col-12">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h4 class="mb-0"><i class="bi bi-briefcase"></i> Your Deals</h4>
            <div class="input-group" style="max-width: 300px;">
                <span class="input-group-text"><i class="bi bi-search"></i></span>
                <input type="text" class="form-control" id="searchDeals" placeholder="Search deals...">
            </div>
        </div>
    </div>
</div>

{% if deals %}
<div class="row" id="dealsContainer">
    {% for deal in deals %}
    <div class="col-lg-4 col-md-6 mb-4 deal-item">
        <div class="card deal-card {{ deal.status }}">
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <h5 class="card-title mb-0 text-truncate" style="max-width: 200px;">{{ deal.name }}</h5>
                    <span class="badge bg-{{ 'success' if deal.status == 'active' else 'warning' if deal.status == 'pending' else 'danger' }}">
                        {{ deal.status|title }}
                    </span>
                </div>
                <p class="text-muted mb-2">
                    <i class="bi bi-building"></i> {{ deal.industry or 'Industry not set' }}
                </p>
                <p class="mb-2">
                    <strong>Amount:</strong> 
                    {% if deal.loan_amount %}
                        ₦{{ "{:,.2f}".format(deal.loan_amount) }}
                    {% else %}
                        Not specified
                    {% endif %}
                </p>
                <p class="text-muted small mb-3 text-truncate">{{ deal.loan_purpose or 'No purpose specified' }}</p>

                <div class="d-flex justify-content-between align-items-center">
                    <small class="text-muted">
                        <i class="bi bi-calendar"></i> {{ deal.created_at[:10] }}
                    </small>
                    <a href="{{ url_for('deal_detail', deal_id=deal.id) }}" class="btn btn-sm btn-outline-primary">
                        Open Deal <i class="bi bi-arrow-right"></i>
                    </a>
                </div>
            </div>
        </div>
    </div>
    {% endfor %}
</div>
{% else %}
<div class="card">
    <div class="card-body empty-state">
        <i class="bi bi-folder-plus"></i>
        <h5>No deals yet</h5>
        <p>Create your first deal to get started with Credit Copilot.</p>
        <a href="{{ url_for('new_deal') }}" class="btn btn-primary">
            <i class="bi bi-plus-lg"></i> Create Deal
        </a>
    </div>
</div>
{% endif %}

{% endblock %}

{% block extra_js %}
<script>
document.getElementById('searchDeals').addEventListener('input', function(e) {
    const searchTerm = e.target.value.toLowerCase();
    document.querySelectorAll('.deal-item').forEach(item => {
        const text = item.textContent.toLowerCase();
        item.style.display = text.includes(searchTerm) ? '' : 'none';
    });
});
</script>
{% endblock %}

"""

NEW_DEAL_TEMPLATE = """
{% extends "base.html" %}

{% block title %}Create New Deal - Credit Copilot{% endblock %}

{% block content %}
<div class="row justify-content-center">
    <div class="col-lg-8">
        <div class="card">
            <div class="card-header">
                <i class="bi bi-plus-circle"></i> Create New Deal
            </div>
            <div class="card-body p-4">
                <form method="POST" action="{{ url_for('new_deal') }}">
                    <div class="mb-3">
                        <label class="form-label">Company / Customer Name *</label>
                        <input type="text" class="form-control" name="name" required 
                               placeholder="e.g., ABC Manufacturing Ltd">
                    </div>

                    <div class="mb-3">
                        <label class="form-label">Industry / Sector</label>
                        <select class="form-select" name="industry">
                            <option value="">Select Industry</option>
                            <option value="Manufacturing">Manufacturing</option>
                            <option value="Agriculture">Agriculture</option>
                            <option value="Retail & Trade">Retail & Trade</option>
                            <option value="Construction">Construction</option>
                            <option value="Healthcare">Healthcare</option>
                            <option value="Technology">Technology</option>
                            <option value="Logistics">Logistics</option>
                            <option value="Real Estate">Real Estate</option>
                            <option value="Education">Education</option>
                            <option value="Energy">Energy</option>
                            <option value="Financial Services">Financial Services</option>
                            <option value="Other">Other</option>
                        </select>
                    </div>

                    <div class="mb-3">
                        <label class="form-label">Requested Loan Amount (₦)</label>
                        <input type="number" class="form-control" name="loan_amount" 
                               placeholder="e.g., 50000000" step="0.01">
                    </div>

                    <div class="mb-4">
                        <label class="form-label">Loan Purpose</label>
                        <textarea class="form-control" name="loan_purpose" rows="3" 
                                  placeholder="Describe the purpose of the loan..."></textarea>
                    </div>

                    <div class="d-flex gap-2">
                        <button type="submit" class="btn btn-primary">
                            <i class="bi bi-check-lg"></i> Create Deal
                        </button>
                        <a href="{{ url_for('index') }}" class="btn btn-outline-secondary">
                            Cancel
                        </a>
                    </div>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}

"""

DEAL_DETAIL_TEMPLATE = """
{% extends "base.html" %}

{% block title %}{{ deal.name }} - Credit Copilot{% endblock %}

{% block content %}
<!-- Deal Header -->
<div class="row mb-4">
    <div class="col-12">
        <div class="d-flex justify-content-between align-items-start flex-wrap">
            <div>
                <nav aria-label="breadcrumb">
                    <ol class="breadcrumb">
                        <li class="breadcrumb-item"><a href="{{ url_for('index') }}">Dashboard</a></li>
                        <li class="breadcrumb-item active">{{ deal.name }}</li>
                    </ol>
                </nav>
                <h2 class="mb-1">{{ deal.name }}</h2>
                <p class="text-muted mb-0">
                    <span class="badge bg-{{ 'success' if deal.status == 'active' else 'warning' if deal.status == 'pending' else 'danger' }}">
                        {{ deal.status|title }}
                    </span>
                    <span class="ms-2"><i class="bi bi-building"></i> {{ deal.industry or 'Industry not set' }}</span>
                    <span class="ms-2"><i class="bi bi-cash-stack"></i> 
                        {% if deal.loan_amount %}₦{{ "{:,.2f}".format(deal.loan_amount) }}{% else %}Amount not set{% endif %}
                    </span>
                </p>
            </div>
            <div class="d-flex gap-2 mt-2 mt-md-0">
                <a href="{{ url_for('delete_deal', deal_id=deal.id) }}" class="btn btn-outline-danger btn-sm" 
                   onclick="return confirm('Are you sure you want to delete this deal? This cannot be undone.')">
                    <i class="bi bi-trash"></i> Delete
                </a>
            </div>
        </div>
    </div>
</div>

<!-- Progress Tracker -->
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-body">
                <div class="progress-tracker">
                    <div class="progress-step completed">
                        <div class="step-circle"><i class="bi bi-check"></i></div>
                        <div class="step-label">Deal Created</div>
                    </div>
                    <div class="progress-step {{ 'completed' if meetings else 'active' }}">
                        <div class="step-circle">{% if meetings %}<i class="bi bi-check"></i>{% else %}2{% endif %}</div>
                        <div class="step-label">Meeting</div>
                    </div>
                    <div class="progress-step {{ 'completed' if documents else 'active' if meetings else '' }}">
                        <div class="step-circle">{% if documents %}<i class="bi bi-check"></i>{% else %}3{% endif %}</div>
                        <div class="step-label">Documents</div>
                    </div>
                    <div class="progress-step {{ 'completed' if financials else 'active' if documents else '' }}">
                        <div class="step-circle">{% if financials %}<i class="bi bi-check"></i>{% else %}4{% endif %}</div>
                        <div class="step-label">Analysis</div>
                    </div>
                    <div class="progress-step {{ 'completed' if deal.facility_amount else 'active' if financials else '' }}">
                        <div class="step-circle">{% if deal.facility_amount %}<i class="bi bi-check"></i>{% else %}5{% endif %}</div>
                        <div class="step-label">Facility</div>
                    </div>
                    <div class="progress-step {{ 'completed' if deal.memo_content else 'active' if deal.facility_amount else '' }}">
                        <div class="step-circle">{% if deal.memo_content %}<i class="bi bi-check"></i>{% else %}6{% endif %}</div>
                        <div class="step-label">Memo</div>
                    </div>
                    <div class="progress-step {{ 'active' if reviews else '' }}">
                        <div class="step-circle">7</div>
                        <div class="step-label">Review</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Main Content Tabs -->
<div class="row">
    <div class="col-12">
        <div class="card">
            <div class="card-header p-0">
                <ul class="nav nav-tabs" id="dealTabs" role="tablist">
                    <li class="nav-item" role="presentation">
                        <button class="nav-link active" id="overview-tab" data-bs-toggle="tab" data-bs-target="#overview" type="button">
                            <i class="bi bi-house-door"></i> Overview
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="meeting-tab" data-bs-toggle="tab" data-bs-target="#meeting" type="button">
                            <i class="bi bi-mic"></i> Meeting
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="documents-tab" data-bs-toggle="tab" data-bs-target="#documents" type="button">
                            <i class="bi bi-files"></i> Documents
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="financial-tab" data-bs-toggle="tab" data-bs-target="#financial" type="button">
                            <i class="bi bi-graph-up"></i> Financial Analysis
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="facility-tab" data-bs-toggle="tab" data-bs-target="#facility" type="button">
                            <i class="bi bi-bank"></i> Facility
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="memo-tab" data-bs-toggle="tab" data-bs-target="#memo" type="button">
                            <i class="bi bi-file-text"></i> Credit Memo
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="review-tab" data-bs-toggle="tab" data-bs-target="#review" type="button">
                            <i class="bi bi-chat-left-text"></i> Credit Review
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="ai-tab" data-bs-toggle="tab" data-bs-target="#ai" type="button">
                            <i class="bi bi-robot"></i> AI Assistant
                        </button>
                    </li>
                </ul>
            </div>

            <div class="card-body">
                <div class="tab-content" id="dealTabContent">

                    <!-- OVERVIEW TAB -->
                    <div class="tab-pane fade show active" id="overview" role="tabpanel">
                        <div class="row">
                            <div class="col-md-6">
                                <div class="section-title"><i class="bi bi-info-circle"></i> Deal Information</div>
                                <table class="table table-borderless">
                                    <tr><td class="text-muted">Company Name</td><td class="fw-medium">{{ deal.name }}</td></tr>
                                    <tr><td class="text-muted">Industry</td><td>{{ deal.industry or '-' }}</td></tr>
                                    <tr><td class="text-muted">Loan Amount</td><td>{% if deal.loan_amount %}₦{{ "{:,.2f}".format(deal.loan_amount) }}{% else %}-{% endif %}</td></tr>
                                    <tr><td class="text-muted">Loan Purpose</td><td>{{ deal.loan_purpose or '-' }}</td></tr>
                                    <tr><td class="text-muted">Created</td><td>{{ deal.created_at[:19] }}</td></tr>
                                    <tr><td class="text-muted">Last Updated</td><td>{{ deal.updated_at[:19] }}</td></tr>
                                </table>
                            </div>
                            <div class="col-md-6">
                                <div class="section-title"><i class="bi bi-clipboard-data"></i> Quick Stats</div>
                                <div class="ratio-grid">
                                    <div class="ratio-item">
                                        <div class="ratio-value">{{ meetings|length }}</div>
                                        <div class="ratio-label">Meetings</div>
                                    </div>
                                    <div class="ratio-item">
                                        <div class="ratio-value">{{ documents|length }}</div>
                                        <div class="ratio-label">Documents</div>
                                    </div>
                                    <div class="ratio-item">
                                        <div class="ratio-value">{{ financials|length }}</div>
                                        <div class="ratio-label">Analyses</div>
                                    </div>
                                    <div class="ratio-item">
                                        <div class="ratio-value">{{ reviews|length }}</div>
                                        <div class="ratio-label">Reviews</div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {% if deal.business_overview %}
                        <div class="mt-4">
                            <div class="section-title"><i class="bi bi-building"></i> Business Overview</div>
                            <div class="p-3 bg-light rounded">{{ deal.business_overview }}</div>
                        </div>
                        {% endif %}

                        {% if deal.initial_risks %}
                        <div class="mt-4">
                            <div class="section-title"><i class="bi bi-exclamation-triangle"></i> Initial Risks</div>
                            <div class="p-3 bg-light rounded">{{ deal.initial_risks }}</div>
                        </div>
                        {% endif %}
                    </div>

                    <!-- MEETING TAB -->
                    <div class="tab-pane fade" id="meeting" role="tabpanel">
                        <div class="row">
                            <div class="col-lg-5">
                                <div class="card">
                                    <div class="card-header">
                                        <i class="bi bi-plus-circle"></i> Capture Meeting
                                    </div>
                                    <div class="card-body">
                                        <form method="POST" action="{{ url_for('add_meeting', deal_id=deal.id) }}">
                                            <div class="mb-3">
                                                <label class="form-label">Meeting Transcript</label>
                                                <textarea class="form-control" name="transcript" rows="6" 
                                                          placeholder="Paste Teams/Zoom transcript here..."></textarea>
                                                <div class="form-text">Paste transcript from Microsoft Teams, Zoom, or other meeting tools.</div>
                                            </div>
                                            <div class="mb-3">
                                                <label class="form-label">Meeting Notes</label>
                                                <textarea class="form-control" name="notes" rows="4" 
                                                          placeholder="Your typed notes from the meeting..."></textarea>
                                            </div>
                                            <div class="mb-3">
                                                <label class="form-label">AI Summary</label>
                                                <textarea class="form-control" name="summary" rows="3" 
                                                          placeholder="AI-generated summary will appear here (or type manually)..."></textarea>
                                            </div>
                                            <button type="submit" class="btn btn-primary w-100">
                                                <i class="bi bi-save"></i> Save Meeting
                                            </button>
                                        </form>
                                    </div>
                                </div>
                            </div>
                            <div class="col-lg-7">
                                <div class="section-title"><i class="bi bi-clock-history"></i> Meeting History</div>
                                {% if meetings %}
                                    {% for meeting in meetings %}
                                    <div class="card mb-3">
                                        <div class="card-body">
                                            <div class="d-flex justify-content-between mb-2">
                                                <small class="text-muted">
                                                    <i class="bi bi-calendar"></i> {{ meeting.created_at[:19] }}
                                                </small>
                                            </div>
                                            {% if meeting.summary %}
                                            <div class="mb-2">
                                                <span class="ai-badge">AI Summary</span>
                                                <p class="mt-2 mb-0">{{ meeting.summary }}</p>
                                            </div>
                                            {% endif %}
                                            {% if meeting.transcript %}
                                            <details class="mt-2">
                                                <summary class="text-primary" style="cursor: pointer;">
                                                    <i class="bi bi-text-left"></i> View Transcript
                                                </summary>
                                                <div class="mt-2 p-2 bg-light rounded small" style="max-height: 200px; overflow-y: auto;">
                                                    {{ meeting.transcript[:500] }}{% if meeting.transcript|length > 500 %}...{% endif %}
                                                </div>
                                            </details>
                                            {% endif %}
                                            {% if meeting.notes %}
                                            <details class="mt-2">
                                                <summary class="text-primary" style="cursor: pointer;">
                                                    <i class="bi bi-journal-text"></i> View Notes
                                                </summary>
                                                <div class="mt-2 p-2 bg-light rounded small">
                                                    {{ meeting.notes }}
                                                </div>
                                            </details>
                                            {% endif %}
                                        </div>
                                    </div>
                                    {% endfor %}
                                {% else %}
                                    <div class="empty-state">
                                        <i class="bi bi-mic-mute"></i>
                                        <p>No meetings captured yet.</p>
                                    </div>
                                {% endif %}
                            </div>
                        </div>
                    </div>

                    <!-- DOCUMENTS TAB -->
                    <div class="tab-pane fade" id="documents" role="tabpanel">
                        <div class="row">
                            <div class="col-lg-4">
                                <div class="card">
                                    <div class="card-header">
                                        <i class="bi bi-upload"></i> Upload Document
                                    </div>
                                    <div class="card-body">
                                        <form method="POST" action="{{ url_for('upload_document', deal_id=deal.id) }}" 
                                              enctype="multipart/form-data">
                                            <div class="mb-3">
                                                <label class="form-label">Document Type</label>
                                                <select class="form-select" name="doc_type">
                                                    <option value="financial_statements">Financial Statements</option>
                                                    <option value="bank_statements">Bank Statements</option>
                                                    <option value="management_accounts">Management Accounts</option>
                                                    <option value="loan_application">Loan Application</option>
                                                    <option value="contracts">Contracts</option>
                                                    <option value="purchase_orders">Purchase Orders</option>
                                                    <option value="invoices">Invoices</option>
                                                    <option value="cac_documents">CAC Documents</option>
                                                    <option value="photos">Photos</option>
                                                    <option value="other">Other</option>
                                                </select>
                                            </div>
                                            <div class="mb-3">
                                                <label class="form-label">Select File</label>
                                                <input type="file" class="form-control" name="file" required>
                                                <div class="form-text">PDF, Word, Excel, CSV, Images (max 50MB)</div>
                                            </div>
                                            <button type="submit" class="btn btn-primary w-100">
                                                <i class="bi bi-cloud-upload"></i> Upload
                                            </button>
                                        </form>
                                    </div>
                                </div>
                            </div>
                            <div class="col-lg-8">
                                <div class="section-title"><i class="bi bi-folder"></i> Document Library</div>
                                {% if documents %}
                                    <div class="row">
                                        {% for doc in documents %}
                                        <div class="col-md-6 mb-3">
                                            <div class="document-item">
                                                {% if doc.doc_type == 'financial_statements' %}
                                                    <i class="bi bi-file-earmark-bar-graph"></i>
                                                {% elif doc.doc_type == 'bank_statements' %}
                                                    <i class="bi bi-bank"></i>
                                                {% elif doc.doc_type == 'contracts' %}
                                                    <i class="bi bi-file-earmark-text"></i>
                                                {% elif doc.doc_type == 'invoices' %}
                                                    <i class="bi bi-receipt"></i>
                                                {% elif doc.doc_type == 'photos' %}
                                                    <i class="bi bi-image"></i>
                                                {% else %}
                                                    <i class="bi bi-file-earmark"></i>
                                                {% endif %}
                                                <div class="flex-grow-1">
                                                    <div class="fw-medium text-truncate" style="max-width: 200px;">{{ doc.filename }}</div>
                                                    <small class="text-muted">{{ doc.doc_type.replace('_', ' ')|title }}</small>
                                                </div>
                                                <a href="{{ url_for('uploaded_file', filename=doc.filepath.replace('uploads/', '')) }}" 
                                                   class="btn btn-sm btn-outline-primary" target="_blank">
                                                    <i class="bi bi-download"></i>
                                                </a>
                                            </div>
                                        </div>
                                        {% endfor %}
                                    </div>
                                {% else %}
                                    <div class="empty-state">
                                        <i class="bi bi-folder-x"></i>
                                        <p>No documents uploaded yet.</p>
                                    </div>
                                {% endif %}
                            </div>
                        </div>
                    </div>

                    <!-- FINANCIAL ANALYSIS TAB -->
                    <div class="tab-pane fade" id="financial" role="tabpanel">
                        <div class="row">
                            <div class="col-lg-5">
                                <div class="card">
                                    <div class="card-header">
                                        <i class="bi bi-calculator"></i> Add Financial Analysis
                                    </div>
                                    <div class="card-body">
                                        <form method="POST" action="{{ url_for('save_financial_analysis', deal_id=deal.id) }}">
                                            <div class="mb-3">
                                                <label class="form-label">Analysis Type</label>
                                                <select class="form-select" name="analysis_type" id="analysisType">
                                                    <option value="financial_statements">Financial Statements Analysis</option>
                                                    <option value="bank_statements">Bank Statement Analysis</option>
                                                    <option value="ratio_analysis">Ratio Analysis</option>
                                                    <option value="cash_flow">Cash Flow Analysis</option>
                                                    <option value="custom">Custom Analysis</option>
                                                </select>
                                            </div>
                                            <div class="mb-3" id="financialForm">
                                                <label class="form-label">Revenue (₦)</label>
                                                <input type="number" class="form-control mb-2" id="revenue" placeholder="Annual Revenue">
                                                <label class="form-label">Net Profit (₦)</label>
                                                <input type="number" class="form-control mb-2" id="netProfit" placeholder="Net Profit">
                                                <label class="form-label">Total Assets (₦)</label>
                                                <input type="number" class="form-control mb-2" id="totalAssets" placeholder="Total Assets">
                                                <label class="form-label">Total Liabilities (₦)</label>
                                                <input type="number" class="form-control mb-2" id="totalLiabilities" placeholder="Total Liabilities">
                                                <label class="form-label">Current Assets (₦)</label>
                                                <input type="number" class="form-control mb-2" id="currentAssets" placeholder="Current Assets">
                                                <label class="form-label">Current Liabilities (₦)</label>
                                                <input type="number" class="form-control mb-2" id="currentLiabilities" placeholder="Current Liabilities">
                                                <label class="form-label">Equity (₦)</label>
                                                <input type="number" class="form-control mb-2" id="equity" placeholder="Shareholders Equity">
                                                <label class="form-label">EBITDA (₦)</label>
                                                <input type="number" class="form-control mb-2" id="ebitda" placeholder="EBITDA">
                                                <label class="form-label">Interest Expense (₦)</label>
                                                <input type="number" class="form-control mb-2" id="interestExpense" placeholder="Interest Expense">
                                                <label class="form-label">Existing Debt (₦)</label>
                                                <input type="number" class="form-control mb-2" id="existingDebt" placeholder="Total Existing Debt">
                                            </div>
                                            <div class="mb-3" id="bankForm" style="display:none;">
                                                <label class="form-label">Average Monthly Turnover (₦)</label>
                                                <input type="number" class="form-control mb-2" id="avgTurnover" placeholder="Average Monthly Turnover">
                                                <label class="form-label">Average Monthly Balance (₦)</label>
                                                <input type="number" class="form-control mb-2" id="avgBalance" placeholder="Average Monthly Balance">
                                                <label class="form-label">Largest Inflow (₦)</label>
                                                <input type="number" class="form-control mb-2" id="largestInflow" placeholder="Largest Single Inflow">
                                                <label class="form-label">Largest Outflow (₦)</label>
                                                <input type="number" class="form-control mb-2" id="largestOutflow" placeholder="Largest Single Outflow">
                                                <label class="form-label">Number of Months Analyzed</label>
                                                <input type="number" class="form-control mb-2" id="monthsAnalyzed" placeholder="e.g., 12">
                                                <label class="form-label">Existing Loan Repayments/Month (₦)</label>
                                                <input type="number" class="form-control mb-2" id="loanRepayments" placeholder="Monthly Loan Repayments">
                                            </div>
                                            <div class="mb-3">
                                                <label class="form-label">Analysis Notes / Commentary</label>
                                                <textarea class="form-control" name="data" id="analysisData" rows="4" 
                                                          placeholder="AI-generated or manual commentary..."></textarea>
                                            </div>
                                            <button type="submit" class="btn btn-primary w-100" onclick="prepareAnalysisData()">
                                                <i class="bi bi-save"></i> Save Analysis
                                            </button>
                                        </form>
                                    </div>
                                </div>
                            </div>
                            <div class="col-lg-7">
                                <div class="section-title"><i class="bi bi-graph-up-arrow"></i> Analysis History</div>
                                {% if financials %}
                                    {% for fin in financials %}
                                    <div class="card mb-3">
                                        <div class="card-body">
                                            <div class="d-flex justify-content-between align-items-start mb-2">
                                                <h6 class="mb-0">
                                                    <span class="ai-badge">{{ fin.analysis_type.replace('_', ' ')|title }}</span>
                                                </h6>
                                                <small class="text-muted">{{ fin.created_at[:19] }}</small>
                                            </div>
                                            {% if fin.data %}
                                                <div class="mt-3 p-2 bg-light rounded small">
                                                    <pre style="white-space: pre-wrap; margin: 0;">{{ fin.data }}</pre>
                                                </div>
                                            {% else %}
                                                <p class="text-muted mb-0">No data captured.</p>
                                            {% endif %}
                                        </div>
                                    </div>
                                    {% endfor %}
                                {% else %}
                                    <div class="empty-state">
                                        <i class="bi bi-graph-down"></i>
                                        <p>No financial analysis yet.</p>
                                    </div>
                                {% endif %}
                            </div>
                        </div>
                    </div>

                    <!-- FACILITY TAB -->
                    <div class="tab-pane fade" id="facility" role="tabpanel">
                        <div class="row">
                            <div class="col-lg-6">
                                <div class="card">
                                    <div class="card-header">
                                        <i class="bi bi-bank"></i> Facility Recommendation
                                    </div>
                                    <div class="card-body">
                                        <form method="POST" action="{{ url_for('save_facility', deal_id=deal.id) }}">
                                            <div class="mb-3">
                                                <label class="form-label">Recommended Facility Amount (₦)</label>
                                                <input type="number" class="form-control" name="facility_amount" 
                                                       value="{{ deal.facility_amount or '' }}" step="0.01"
                                                       placeholder="e.g., 50000000">
                                            </div>
                                            <div class="mb-3">
                                                <label class="form-label">Tenor</label>
                                                <select class="form-select" name="facility_tenor">
                                                    <option value="">Select Tenor</option>
                                                    <option value="3 months" {{ 'selected' if deal.facility_tenor == '3 months' else '' }}>3 Months</option>
                                                    <option value="6 months" {{ 'selected' if deal.facility_tenor == '6 months' else '' }}>6 Months</option>
                                                    <option value="12 months" {{ 'selected' if deal.facility_tenor == '12 months' else '' }}>12 Months</option>
                                                    <option value="18 months" {{ 'selected' if deal.facility_tenor == '18 months' else '' }}>18 Months</option>
                                                    <option value="24 months" {{ 'selected' if deal.facility_tenor == '24 months' else '' }}>24 Months</option>
                                                    <option value="36 months" {{ 'selected' if deal.facility_tenor == '36 months' else '' }}>36 Months</option>
                                                    <option value="48 months" {{ 'selected' if deal.facility_tenor == '48 months' else '' }}>48 Months</option>
                                                    <option value="60 months" {{ 'selected' if deal.facility_tenor == '60 months' else '' }}>60 Months</option>
                                                </select>
                                            </div>
                                            <div class="mb-3">
                                                <label class="form-label">Repayment Frequency</label>
                                                <select class="form-select" name="facility_repayment">
                                                    <option value="">Select Frequency</option>
                                                    <option value="Monthly" {{ 'selected' if deal.facility_repayment == 'Monthly' else '' }}>Monthly</option>
                                                    <option value="Quarterly" {{ 'selected' if deal.facility_repayment == 'Quarterly' else '' }}>Quarterly</option>
                                                    <option value="Semi-annually" {{ 'selected' if deal.facility_repayment == 'Semi-annually' else '' }}>Semi-annually</option>
                                                    <option value="Bullet (at maturity)" {{ 'selected' if deal.facility_repayment == 'Bullet (at maturity)' else '' }}>Bullet (at maturity)</option>
                                                </select>
                                            </div>
                                            <div class="mb-3">
                                                <label class="form-label">Conditions Precedent</label>
                                                <textarea class="form-control" name="facility_conditions" rows="3"
                                                          placeholder="List conditions that must be met before disbursement...">{{ deal.facility_conditions or '' }}</textarea>
                                            </div>
                                            <div class="mb-3">
                                                <label class="form-label">Covenants</label>
                                                <textarea class="form-control" name="facility_covenants" rows="3"
                                                          placeholder="Financial and non-financial covenants...">{{ deal.facility_covenants or '' }}</textarea>
                                            </div>
                                            <div class="mb-3">
                                                <label class="form-label">Collateral / Security</label>
                                                <textarea class="form-control" name="facility_collateral" rows="3"
                                                          placeholder="Describe collateral and security package...">{{ deal.facility_collateral or '' }}</textarea>
                                            </div>
                                            <div class="mb-3">
                                                <label class="form-label">Justification <span class="text-danger">*</span></label>
                                                <textarea class="form-control" name="facility_justification" rows="5" required
                                                          placeholder="Explain WHY this facility structure is recommended. Reference financial analysis, cash flow, collateral, and risk mitigation...">{{ deal.facility_justification or '' }}</textarea>
                                                <div class="form-text text-danger">Every recommendation must include justification.</div>
                                            </div>
                                            <button type="submit" class="btn btn-primary w-100">
                                                <i class="bi bi-save"></i> Save Facility Recommendation
                                            </button>
                                        </form>
                                    </div>
                                </div>
                            </div>
                            <div class="col-lg-6">
                                <div class="section-title"><i class="bi bi-eye"></i> Current Recommendation</div>
                                {% if deal.facility_amount %}
                                <div class="card">
                                    <div class="card-body">
                                        <table class="table table-borderless">
                                            <tr><td class="text-muted">Amount</td><td class="fw-bold fs-5">₦{{ "{:,.2f}".format(deal.facility_amount) }}</td></tr>
                                            <tr><td class="text-muted">Tenor</td><td>{{ deal.facility_tenor or '-' }}</td></tr>
                                            <tr><td class="text-muted">Repayment</td><td>{{ deal.facility_repayment or '-' }}</td></tr>
                                        </table>
                                        {% if deal.facility_conditions %}
                                        <div class="mt-3">
                                            <h6 class="text-muted">Conditions</h6>
                                            <div class="p-2 bg-light rounded small">{{ deal.facility_conditions }}</div>
                                        </div>
                                        {% endif %}
                                        {% if deal.facility_covenants %}
                                        <div class="mt-3">
                                            <h6 class="text-muted">Covenants</h6>
                                            <div class="p-2 bg-light rounded small">{{ deal.facility_covenants }}</div>
                                        </div>
                                        {% endif %}
                                        {% if deal.facility_collateral %}
                                        <div class="mt-3">
                                            <h6 class="text-muted">Collateral</h6>
                                            <div class="p-2 bg-light rounded small">{{ deal.facility_collateral }}</div>
                                        </div>
                                        {% endif %}
                                        {% if deal.facility_justification %}
                                        <div class="mt-3">
                                            <h6 class="text-muted">Justification</h6>
                                            <div class="p-2 bg-light rounded small">{{ deal.facility_justification }}</div>
                                        </div>
                                        {% endif %}
                                    </div>
                                </div>
                                {% else %}
                                <div class="empty-state">
                                    <i class="bi bi-bank"></i>
                                    <p>No facility recommendation yet.</p>
                                </div>
                                {% endif %}
                            </div>
                        </div>
                    </div>

                    <!-- CREDIT MEMO TAB -->
                    <div class="tab-pane fade" id="memo" role="tabpanel">
                        <div class="row">
                            <div class="col-12">
                                <div class="d-flex justify-content-between align-items-center mb-3">
                                    <div class="section-title mb-0"><i class="bi bi-file-text"></i> Credit Memo Editor</div>
                                    <div class="d-flex gap-2">
                                        <button class="btn btn-outline-primary btn-sm" onclick="generateMemoTemplate()">
                                            <i class="bi bi-magic"></i> Generate Template
                                        </button>
                                        <button class="btn btn-accent btn-sm" onclick="document.getElementById('memoForm').submit()">
                                            <i class="bi bi-save"></i> Save Memo
                                        </button>
                                    </div>
                                </div>
                                <form method="POST" action="{{ url_for('save_memo', deal_id=deal.id) }}" id="memoForm">
                                    <textarea class="form-control memo-editor" name="memo_content" id="memoEditor" rows="25"
                                              placeholder="Start writing your credit memo here...">{{ deal.memo_content or '' }}</textarea>
                                </form>
                            </div>
                        </div>
                    </div>

                    <!-- CREDIT REVIEW TAB -->
                    <div class="tab-pane fade" id="review" role="tabpanel">
                        <div class="row">
                            <div class="col-lg-5">
                                <div class="card">
                                    <div class="card-header">
                                        <i class="bi bi-plus-circle"></i> Add Review Question
                                    </div>
                                    <div class="card-body">
                                        <form method="POST" action="{{ url_for('add_review_question', deal_id=deal.id) }}">
                                            <div class="mb-3">
                                                <label class="form-label">Question from Credit Risk</label>
                                                <textarea class="form-control" name="question" rows="4" required
                                                          placeholder="Paste the question from Credit Risk here..."></textarea>
                                            </div>
                                            <div class="mb-3">
                                                <label class="form-label">Your Response</label>
                                                <textarea class="form-control" name="response" rows="6"
                                                          placeholder="Draft your response here. The AI can help you formulate this..."></textarea>
                                            </div>
                                            <button type="submit" class="btn btn-primary w-100">
                                                <i class="bi bi-save"></i> Save Response
                                            </button>
                                        </form>
                                    </div>
                                </div>
                            </div>
                            <div class="col-lg-7">
                                <div class="section-title"><i class="bi bi-chat-dots"></i> Review Q&A</div>
                                {% if reviews %}
                                    {% for review in reviews %}
                                    <div class="card mb-3 {{ 'border-success' if review.response else 'border-warning' }}">
                                        <div class="card-body">
                                            <div class="d-flex justify-content-between mb-2">
                                                <span class="badge bg-{{ 'success' if review.response else 'warning' }}">
                                                    {{ 'Answered' if review.response else 'Pending' }}
                                                </span>
                                                <small class="text-muted">{{ review.created_at[:19] }}</small>
                                            </div>
                                            <div class="mb-3">
                                                <h6 class="text-muted mb-1">Question:</h6>
                                                <div class="p-2 bg-light rounded">{{ review.question }}</div>
                                            </div>
                                            {% if review.response %}
                                            <div>
                                                <h6 class="text-muted mb-1">Response:</h6>
                                                <div class="p-2 bg-light rounded">{{ review.response }}</div>
                                            </div>
                                            {% endif %}
                                        </div>
                                    </div>
                                    {% endfor %}
                                {% else %}
                                    <div class="empty-state">
                                        <i class="bi bi-inbox"></i>
                                        <p>No review questions yet.</p>
                                    </div>
                                {% endif %}
                            </div>
                        </div>
                    </div>

                    <!-- AI ASSISTANT TAB -->
                    <div class="tab-pane fade" id="ai" role="tabpanel">
                        <div class="row">
                            <div class="col-lg-8 mx-auto">
                                <div class="card">
                                    <div class="card-header d-flex justify-content-between align-items-center">
                                        <span><i class="bi bi-robot"></i> Credit Copilot AI</span>
                                        <span class="ai-badge">AI Powered</span>
                                    </div>
                                    <div class="card-body">
                                        <div class="chat-container" id="chatContainer">
                                            {% if chat_messages %}
                                                {% for msg in chat_messages %}
                                                <div class="chat-message {{ msg.role }}">
                                                    <div class="message-bubble">{{ msg.content }}</div>
                                                </div>
                                                {% endfor %}
                                            {% else %}
                                                <div class="text-center text-muted py-5">
                                                    <i class="bi bi-robot" style="font-size: 3rem;"></i>
                                                    <p class="mt-3">I'm your Credit Copilot AI assistant.</p>
                                                    <p class="small">I can help you with:<br>
                                                    • Analyzing financial statements<br>
                                                    • Drafting credit memos<br>
                                                    • Reviewing bank statements<br>
                                                    • Responding to credit questions<br>
                                                    • Industry research<br>
                                                    • Facility recommendations</p>
                                                </div>
                                            {% endif %}
                                        </div>
                                        <div class="mt-3">
                                            <div class="input-group">
                                                <input type="text" class="form-control" id="chatInput" 
                                                       placeholder="Ask me anything about this deal..."
                                                       onkeypress="if(event.key==='Enter') sendMessage()">
                                                <button class="btn btn-primary" onclick="sendMessage()">
                                                    <i class="bi bi-send"></i>
                                                </button>
                                            </div>
                                            <div class="mt-2 d-flex gap-2 flex-wrap">
                                                <button class="btn btn-sm btn-outline-secondary" onclick="quickAsk('Analyze the financials')">
                                                    Analyze Financials
                                                </button>
                                                <button class="btn btn-sm btn-outline-secondary" onclick="quickAsk('Review this memo')">
                                                    Review Memo
                                                </button>
                                                <button class="btn btn-sm btn-outline-secondary" onclick="quickAsk('Challenge my recommendation')">
                                                    Challenge Recommendation
                                                </button>
                                                <button class="btn btn-sm btn-outline-secondary" onclick="quickAsk('Head of Credit review')">
                                                    Head of Credit Mode
                                                </button>
                                                <button class="btn btn-sm btn-outline-secondary" onclick="quickAsk('Generate industry outlook')">
                                                    Industry Outlook
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                </div>
            </div>
        </div>
    </div>
</div>

{% endblock %}

{% block extra_js %}
<script>
// Analysis type toggle
document.getElementById('analysisType').addEventListener('change', function() {
    const type = this.value;
    document.getElementById('financialForm').style.display = 
        (type === 'financial_statements' || type === 'ratio_analysis') ? 'block' : 'none';
    document.getElementById('bankForm').style.display = 
        (type === 'bank_statements') ? 'block' : 'none';
});

function prepareAnalysisData() {
    const type = document.getElementById('analysisType').value;
    let data = {};

    if (type === 'financial_statements' || type === 'ratio_analysis') {
        const revenue = parseFloat(document.getElementById('revenue').value) || 0;
        const netProfit = parseFloat(document.getElementById('netProfit').value) || 0;
        const totalAssets = parseFloat(document.getElementById('totalAssets').value) || 0;
        const totalLiabilities = parseFloat(document.getElementById('totalLiabilities').value) || 0;
        const currentAssets = parseFloat(document.getElementById('currentAssets').value) || 0;
        const currentLiabilities = parseFloat(document.getElementById('currentLiabilities').value) || 0;
        const equity = parseFloat(document.getElementById('equity').value) || 0;
        const ebitda = parseFloat(document.getElementById('ebitda').value) || 0;
        const interestExpense = parseFloat(document.getElementById('interestExpense').value) || 0;
        const existingDebt = parseFloat(document.getElementById('existingDebt').value) || 0;

        data = {
            revenue: revenue,
            net_profit: netProfit,
            total_assets: totalAssets,
            total_liabilities: totalLiabilities,
            current_assets: currentAssets,
            current_liabilities: currentLiabilities,
            equity: equity,
            ebitda: ebitda,
            interest_expense: interestExpense,
            existing_debt: existingDebt,
            current_ratio: currentLiabilities > 0 ? currentAssets / currentLiabilities : 0,
            debt_equity: equity > 0 ? totalLiabilities / equity : 0,
            roe: equity > 0 ? (netProfit / equity) * 100 : 0,
            net_margin: revenue > 0 ? (netProfit / revenue) * 100 : 0,
            interest_coverage: interestExpense > 0 ? ebitda / interestExpense : 0,
            dscr: existingDebt > 0 ? ebitda / existingDebt : 0
        };
    } else if (type === 'bank_statements') {
        data = {
            avg_monthly_turnover: parseFloat(document.getElementById('avgTurnover').value) || 0,
            avg_monthly_balance: parseFloat(document.getElementById('avgBalance').value) || 0,
            largest_inflow: parseFloat(document.getElementById('largestInflow').value) || 0,
            largest_outflow: parseFloat(document.getElementById('largestOutflow').value) || 0,
            months_analyzed: parseInt(document.getElementById('monthsAnalyzed').value) || 0,
            loan_repayments: parseFloat(document.getElementById('loanRepayments').value) || 0
        };
    }

    const notes = document.getElementById('analysisData').value;
    const fullData = { ...data, notes: notes };
    document.getElementById('analysisData').value = JSON.stringify(fullData, null, 2);
}

// Memo template generator
function generateMemoTemplate() {
    const template = `CREDIT MEMORANDUM

1.  BORROWER DETAILS
    Company Name:     {{ deal.name }}
    Industry:           {{ deal.industry or 'N/A' }}
    Date:               ${new Date().toLocaleDateString()}

2.  FACILITY REQUESTED
    Amount:             {{ 'N' + "{:,.2f}".format(deal.loan_amount) if deal.loan_amount else 'TBD' }}
    Purpose:            {{ deal.loan_purpose or 'N/A' }}

3.  BUSINESS OVERVIEW
    [Describe the borrower's business model, history, market position, and key management]

4.  FINANCIAL ANALYSIS
    [Insert financial ratios, trends, and commentary here]

    Key Ratios:
    - Current Ratio:    
    - Debt/Equity:      
    - Interest Cover:   
    - DSCR:             

5.  BANK STATEMENT ANALYSIS
    [Insert turnover trends, balance analysis, and cash flow commentary]

6.  INDUSTRY & MARKET ANALYSIS
    [Insert industry outlook, competitive position, and sector risks]

7.  FACILITY RECOMMENDATION
    Amount:             {{ 'N' + "{:,.2f}".format(deal.facility_amount) if deal.facility_amount else 'TBD' }}
    Tenor:              {{ deal.facility_tenor or 'TBD' }}
    Repayment:          {{ deal.facility_repayment or 'TBD' }}

    Justification:
    {{ deal.facility_justification or '[Provide detailed justification]' }}

8.  COLLATERAL & SECURITY
    {{ deal.facility_collateral or '[Describe security package]' }}

9.  COVENANTS & CONDITIONS
    {{ deal.facility_covenants or '[List covenants]' }}

    Conditions Precedent:
    {{ deal.facility_conditions or '[List conditions]' }}

10. RISK ASSESSMENT
    [Key risks and mitigants]

11. RECOMMENDATION
    [Final recommendation with clear rationale]

Prepared by: [Your Name]
Date: ${new Date().toLocaleDateString()}`;

    document.getElementById('memoEditor').value = template;
}

// AI Chat functionality
function sendMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    if (!message) return;

    addMessageToChat('user', message);
    input.value = '';

    fetch(`/deal/{{ deal.id }}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: 'user', content: message })
    }).then(() => {
        generateAIResponse(message);
    });
}

function quickAsk(prompt) {
    document.getElementById('chatInput').value = prompt;
    sendMessage();
}

function addMessageToChat(role, content) {
    const container = document.getElementById('chatContainer');
    // Remove empty state if present
    const emptyState = container.querySelector('.text-center');
    if (emptyState) emptyState.remove();

    const div = document.createElement('div');
    div.className = `chat-message ${role}`;
    div.innerHTML = `<div class="message-bubble">${content.replace(/\n/g, '<br>')}</div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function generateAIResponse(userMessage) {
    const dealName = "{{ deal.name }}";
    const industry = "{{ deal.industry or 'the industry' }}";
    const amount = "{{ 'N' + "{:,.2f}".format(deal.loan_amount) if deal.loan_amount else 'the requested amount' }}";

    let response = '';
    const lowerMsg = userMessage.toLowerCase();

    if (lowerMsg.includes('analyze') && lowerMsg.includes('financial')) {
        response = `I've reviewed the financial data for ${dealName}. Here are my observations:

**Liquidity:** The current ratio indicates [assess based on data]. A ratio above 1.5x is generally comfortable for ${industry}.

**Leverage:** The debt-to-equity position suggests [assess]. For this sector, we typically look for D/E below 2.0x.

**Profitability:** The net margin of [X%] is [above/below] industry average for ${industry}.

**Repayment Capacity:** The DSCR of [X]x and interest coverage of [Y]x indicate [strong/adequate/weak] capacity to service debt.

**Recommendation:** [Tailored recommendation based on ratios].`;
    } else if (lowerMsg.includes('review') && lowerMsg.includes('memo')) {
        response = `I've reviewed your credit memo for ${dealName}. Here are my suggestions:

**Strengths:**
• Clear facility structure
• Good collateral description

**Areas to Strengthen:**
• Add more detail on industry risks specific to ${industry}
• Quantify the repayment capacity with specific DSCR calculations
• Include stress-test scenarios (e.g., 20% revenue decline)
• Clarify the use of proceeds with a disbursement schedule

**Missing Elements:**
• Environmental/social risk assessment
• Related party exposure
• Contingent liabilities

Would you like me to help draft any of these sections?`;
    } else if (lowerMsg.includes('challenge')) {
        response = `Let me challenge your recommendation for ${dealName}:

**Counter-arguments:**
1. The requested amount of ${amount} may be aggressive given the [financial metrics]. Have you considered a phased approach?

2. The tenor of [X months] doesn't align with the asset conversion cycle. Should it be shorter/longer?

3. The collateral coverage of [X%] is [adequate/marginal]. What happens in a 30% decline scenario?

4. Industry headwinds in ${industry} suggest [specific risk]. How is this mitigated?

5. The borrower's concentration risk with [top customer] represents [X%] of revenue. What if they default?

**My Alternative View:**
Consider reducing to [Y amount] with stricter covenants and quarterly reviews.

Can you address these concerns?`;
    } else if (lowerMsg.includes('head of credit') || lowerMsg.includes('hoc')) {
        response = `**HEAD OF CREDIT REVIEW - ${dealName}**

I'm reviewing this as Head of Credit would:

**Red Flags:**
□ [List any red flags from the deal data]

**Questions I Would Ask:**
1. Why is the facility amount justified at this level?
2. What's the borrower's track record with existing lenders?
3. How does this compare to our exposure limits for ${industry}?
4. What's the exit strategy if performance deteriorates?
5. Are there any governance concerns with the board/management?

**Memo Quality:**
□ Structure: [Good/Needs work]
□ Justification: [Strong/Weak]
□ Risk Assessment: [Comprehensive/Superficial]
□ Financial Analysis: [Detailed/High-level]

**Overall Assessment:**
[Approve with conditions / Return for revision / Decline]

**Required Changes Before Submission:**
• [Specific changes needed]`;
    } else if (lowerMsg.includes('industry') || lowerMsg.includes('outlook')) {
        response = `**Industry Outlook: ${industry}**

**Current Market Conditions:**
The ${industry} sector in Nigeria is currently experiencing [trends based on general knowledge]. Key drivers include [macro factors].

**Regulatory Environment:**
• [Relevant CBN policies]
• [Sector-specific regulations]

**Key Risks:**
1. [Supply chain risks]
2. [Foreign exchange exposure]
3. [Demand volatility]
4. [Competition intensity]

**Opportunities:**
1. [Government incentives]
2. [Export potential]
3. [Technology adoption]

**Benchmark Metrics for ${industry}:**
• Average DSCR: [X]x
• Typical collateral coverage: [Y]%
• Standard tenor: [Z] months

**Recommendation:**
This sector is [favorable/neutral/challenging] for lending. Ensure [specific safeguards].`;
    } else {
        response = `I understand you're asking about: "${userMessage}"

For ${dealName} in the ${industry} sector, I can help you with:

• Analyzing the financial statements and calculating key ratios
• Reviewing bank statement trends and cash flow patterns
• Drafting or refining the credit memo sections
• Preparing responses to credit review questions
• Challenging your recommendation to make it stronger
• Simulating Head of Credit review questions

Could you be more specific about what you'd like me to focus on? Or try one of the quick-action buttons below.`;
    }

    setTimeout(() => {
        addMessageToChat('assistant', response);
        fetch(`/deal/{{ deal.id }}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ role: 'assistant', content: response })
        });
    }, 800);
}

// Scroll chat to bottom on load
document.addEventListener('DOMContentLoaded', function() {
    const chatContainer = document.getElementById('chatContainer');
    if (chatContainer) {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
});
</script>
{% endblock %}

"""


@app.route("/")
def index():
    conn = get_db()
    deals = conn.execute("SELECT * FROM deals ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template_string(INDEX_TEMPLATE, deals=deals)

@app.route("/deal/new", methods=["GET", "POST"])
def new_deal():
    if request.method == "POST":
        deal_id = str(uuid.uuid4())
        name = request.form["name"]
        industry = request.form.get("industry", "")
        loan_amount = request.form.get("loan_amount", 0)
        loan_purpose = request.form.get("loan_purpose", "")
        conn = get_db()
        conn.execute("""
            INSERT INTO deals (id, name, industry, loan_amount, loan_purpose, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (deal_id, name, industry, loan_amount, loan_purpose,
              datetime.datetime.now().isoformat(), datetime.datetime.now().isoformat()))
        conn.commit()
        conn.close()
        flash("Deal created successfully!", "success")
        return redirect(url_for("deal_detail", deal_id=deal_id))
    return render_template_string(NEW_DEAL_TEMPLATE)

@app.route("/deal/<deal_id>")
def deal_detail(deal_id):
    conn = get_db()
    deal = conn.execute("SELECT * FROM deals WHERE id = ?", (deal_id,)).fetchone()
    meetings = conn.execute("SELECT * FROM meetings WHERE deal_id = ? ORDER BY created_at DESC", (deal_id,)).fetchall()
    documents = conn.execute("SELECT * FROM documents WHERE deal_id = ? ORDER BY uploaded_at DESC", (deal_id,)).fetchall()
    financials = conn.execute("SELECT * FROM financial_analysis WHERE deal_id = ? ORDER BY created_at DESC", (deal_id,)).fetchall()
    reviews = conn.execute("SELECT * FROM credit_reviews WHERE deal_id = ? ORDER BY created_at DESC", (deal_id,)).fetchall()
    chat_messages = conn.execute("SELECT * FROM chat_messages WHERE deal_id = ? ORDER BY created_at ASC", (deal_id,)).fetchall()
    conn.close()
    return render_template_string(DEAL_DETAIL_TEMPLATE, deal=deal, meetings=meetings,
                           documents=documents, financials=financials,
                           reviews=reviews, chat_messages=chat_messages)

@app.route("/deal/<deal_id>/meeting", methods=["POST"])
def add_meeting(deal_id):
    transcript = request.form.get("transcript", "")
    notes = request.form.get("notes", "")
    summary = request.form.get("summary", "")
    meeting_id = str(uuid.uuid4())
    conn = get_db()
    conn.execute("""
        INSERT INTO meetings (id, deal_id, transcript, notes, summary, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (meeting_id, deal_id, transcript, notes, summary, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()
    flash("Meeting captured successfully!", "success")
    return redirect(url_for("deal_detail", deal_id=deal_id))

@app.route("/deal/<deal_id>/upload", methods=["POST"])
def upload_document(deal_id):
    if "file" not in request.files:
        flash("No file selected", "error")
        return redirect(url_for("deal_detail", deal_id=deal_id))
    file = request.files["file"]
    if file.filename == "":
        flash("No file selected", "error")
        return redirect(url_for("deal_detail", deal_id=deal_id))
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
        file.save(filepath)
        doc_type = request.form.get("doc_type", "other")
        doc_id = str(uuid.uuid4())
        conn = get_db()
        conn.execute("""
            INSERT INTO documents (id, deal_id, filename, filepath, doc_type, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (doc_id, deal_id, filename, filepath, doc_type, datetime.datetime.now().isoformat()))
        conn.commit()
        conn.close()
        flash("Document uploaded successfully!", "success")
    else:
        flash("File type not allowed", "error")
    return redirect(url_for("deal_detail", deal_id=deal_id))

@app.route("/deal/<deal_id>/financial", methods=["POST"])
def save_financial_analysis(deal_id):
    analysis_type = request.form["analysis_type"]
    data = request.form.get("data", "{}")
    analysis_id = str(uuid.uuid4())
    conn = get_db()
    conn.execute("""
        INSERT INTO financial_analysis (id, deal_id, analysis_type, data, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (analysis_id, deal_id, analysis_type, data, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()
    flash("Financial analysis saved!", "success")
    return redirect(url_for("deal_detail", deal_id=deal_id))

@app.route("/deal/<deal_id>/memo", methods=["POST"])
def save_memo(deal_id):
    memo_content = request.form.get("memo_content", "")
    conn = get_db()
    conn.execute("UPDATE deals SET memo_content = ?, updated_at = ? WHERE id = ?",
                 (memo_content, datetime.datetime.now().isoformat(), deal_id))
    conn.commit()
    conn.close()
    flash("Credit memo saved!", "success")
    return redirect(url_for("deal_detail", deal_id=deal_id))

@app.route("/deal/<deal_id>/facility", methods=["POST"])
def save_facility(deal_id):
    facility_amount = request.form.get("facility_amount", "")
    facility_tenor = request.form.get("facility_tenor", "")
    facility_repayment = request.form.get("facility_repayment", "")
    facility_conditions = request.form.get("facility_conditions", "")
    facility_covenants = request.form.get("facility_covenants", "")
    facility_collateral = request.form.get("facility_collateral", "")
    facility_justification = request.form.get("facility_justification", "")
    conn = get_db()
    conn.execute("""
        UPDATE deals SET
            facility_amount = ?, facility_tenor = ?, facility_repayment = ?,
            facility_conditions = ?, facility_covenants = ?, facility_collateral = ?,
            facility_justification = ?, updated_at = ?
        WHERE id = ?
    """, (facility_amount, facility_tenor, facility_repayment, facility_conditions,
          facility_covenants, facility_collateral, facility_justification,
          datetime.datetime.now().isoformat(), deal_id))
    conn.commit()
    conn.close()
    flash("Facility recommendation saved!", "success")
    return redirect(url_for("deal_detail", deal_id=deal_id))

@app.route("/deal/<deal_id>/review", methods=["POST"])
def add_review_question(deal_id):
    question = request.form.get("question", "")
    response = request.form.get("response", "")
    review_id = str(uuid.uuid4())
    conn = get_db()
    conn.execute("""
        INSERT INTO credit_reviews (id, deal_id, question, response, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (review_id, deal_id, question, response, "pending", datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()
    flash("Review question added!", "success")
    return redirect(url_for("deal_detail", deal_id=deal_id))

@app.route("/deal/<deal_id>/chat", methods=["POST"])
def add_chat_message(deal_id):
    data = request.get_json()
    role = data.get("role", "user")
    content = data.get("content", "")
    msg_id = str(uuid.uuid4())
    conn = get_db()
    conn.execute("""
        INSERT INTO chat_messages (id, deal_id, role, content, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (msg_id, deal_id, role, content, datetime.datetime.now().isoformat()))
    conn.commit()
    if role == "user":
        deal = conn.execute("SELECT * FROM deals WHERE id = ?", (deal_id,)).fetchone()
        context = "Company: " + str(deal["name"]) + ", Industry: " + str(deal["industry"] or "N/A") + ", Loan Amount: " + str(deal["loan_amount"] or "N/A")
        ai_response = get_gemini_response(content, context)
        if ai_response:
            ai_msg_id = str(uuid.uuid4())
            conn.execute("""
                INSERT INTO chat_messages (id, deal_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (ai_msg_id, deal_id, "assistant", ai_response, datetime.datetime.now().isoformat()))
            conn.commit()
    conn.close()
    return jsonify({"status": "success", "message_id": msg_id})

@app.route("/deal/<deal_id>/chat/history")
def get_chat_history(deal_id):
    conn = get_db()
    messages = conn.execute("""
        SELECT role, content FROM chat_messages
        WHERE deal_id = ? ORDER BY created_at ASC
    """, (deal_id,)).fetchall()
    conn.close()
    return jsonify([{"role": m["role"], "content": m["content"]} for m in messages])

@app.route("/deal/<deal_id>/delete")
def delete_deal(deal_id):
    conn = get_db()
    conn.execute("DELETE FROM chat_messages WHERE deal_id = ?", (deal_id,))
    conn.execute("DELETE FROM credit_reviews WHERE deal_id = ?", (deal_id,))
    conn.execute("DELETE FROM financial_analysis WHERE deal_id = ?", (deal_id,))
    conn.execute("DELETE FROM documents WHERE deal_id = ?", (deal_id,))
    conn.execute("DELETE FROM meetings WHERE deal_id = ?", (deal_id,))
    conn.execute("DELETE FROM deals WHERE id = ?", (deal_id,))
    conn.commit()
    conn.close()
    flash("Deal deleted successfully!", "success")
    return redirect(url_for("index"))

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route("/api/deal/<deal_id>")
def api_deal_detail(deal_id):
    conn = get_db()
    deal = conn.execute("SELECT * FROM deals WHERE id = ?", (deal_id,)).fetchone()
    meetings = conn.execute("SELECT * FROM meetings WHERE deal_id = ?", (deal_id,)).fetchall()
    documents = conn.execute("SELECT * FROM documents WHERE deal_id = ?", (deal_id,)).fetchall()
    financials = conn.execute("SELECT * FROM financial_analysis WHERE deal_id = ?", (deal_id,)).fetchall()
    reviews = conn.execute("SELECT * FROM credit_reviews WHERE deal_id = ?", (deal_id,)).fetchall()
    conn.close()
    if not deal:
        return jsonify({"error": "Deal not found"}), 404
    return jsonify({
        "deal": dict(deal),
        "meetings": [dict(m) for m in meetings],
        "documents": [dict(d) for d in documents],
        "financials": [dict(f) for f in financials],
        "reviews": [dict(r) for r in reviews]
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
