import sqlite3
import os
import pandas as pd

DB_FILE = os.path.join(os.path.dirname(__file__), "engine.db")
DATASET_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dataset.xlsx"))

def db_connect():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db_connect()
    cursor = conn.cursor()
    
    # Create Workspaces Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS workspaces (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        client TEXT,
        budget TEXT,
        deadline TEXT,
        status TEXT DEFAULT 'Pending' -- Pending, Analysis, Drafting, Review, Completed
    )
    """)
    
    # Create Bid History Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bid_history (
        bid_id TEXT PRIMARY KEY,
        client TEXT,
        sector TEXT,
        budget TEXT,
        score INTEGER,
        outcome TEXT,
        response_time INTEGER,
        compliance INTEGER,
        doc_pages INTEGER,
        gaps_found INTEGER,
        bid_manager TEXT,
        submission_date TEXT
    )
    """)
    
    # Create Capability Library Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS capability_library (
        cap_id TEXT PRIMARY KEY,
        domain TEXT,
        project_summary TEXT,
        certification TEXT,
        year_completed INTEGER,
        contract_value TEXT,
        duration_months INTEGER,
        client_type TEXT
    )
    """)
    
    # Create Compliance Checklist Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS compliance_checklist (
        id TEXT PRIMARY KEY,
        workspace_id TEXT,
        section TEXT,
        description TEXT NOT NULL,
        is_mandatory INTEGER DEFAULT 1,
        status TEXT DEFAULT 'Pending', -- Pending, Pass, Fail, Waived
        matched_evidence TEXT,
        override_status TEXT,
        notes TEXT,
        FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
    )
    """)
    
    # Create Proposal Drafts Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS proposal_drafts (
        id TEXT PRIMARY KEY,
        workspace_id TEXT,
        question_id TEXT,
        question_text TEXT NOT NULL,
        drafted_answer TEXT,
        matched_evidence TEXT,
        comments TEXT,
        FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
    )
    """)

    # Create Capability Chunks Table for Dynamic RAG
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS capability_chunks (
        chunk_id TEXT PRIMARY KEY,
        source_file TEXT,
        content TEXT NOT NULL,
        domain TEXT,
        metadata TEXT
    )
    """)

    # Create Evaluation Criteria Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS evaluation_criteria (
        id TEXT PRIMARY KEY,
        sector TEXT NOT NULL,
        criteria_name TEXT NOT NULL,
        description TEXT,
        weight_range TEXT
    )
    """)

    # Create SOW Plans Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sow_plans (
        workspace_id TEXT PRIMARY KEY,
        milestones TEXT NOT NULL, -- JSON string
        efforts TEXT NOT NULL,    -- JSON string
        costs TEXT NOT NULL,      -- JSON string
        FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
    )
    """)

    # Create Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        role TEXT NOT NULL,
        permissions TEXT NOT NULL -- JSON serialized list of permissions
    )
    """)
    
    conn.commit()
    
    # Seed data from dataset.xlsx if tables are empty
    seed_data(conn)
    conn.close()

def seed_data(conn):
    cursor = conn.cursor()
    
    # 1. Seed Bid History
    cursor.execute("SELECT COUNT(*) FROM bid_history")
    if cursor.fetchone()[0] == 0:
        if os.path.exists(DATASET_PATH):
            try:
                # Read sheets skipping title rows. Headers are in row 2 (0-indexed index 2)
                df_history = pd.read_excel(DATASET_PATH, sheet_name="PS1 – Bid History", header=2)
                # Drop rows that are completely empty
                df_history = df_history.dropna(subset=["Bid ID"])
                
                for _, row in df_history.iterrows():
                    cursor.execute("""
                    INSERT OR REPLACE INTO bid_history 
                    (bid_id, client, sector, budget, score, outcome, response_time, compliance, doc_pages, gaps_found, bid_manager, submission_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        str(row["Bid ID"]),
                        str(row["Client"]),
                        str(row["Sector"]),
                        str(row["Budget"]),
                        int(row["Score (%)"]) if not pd.isna(row["Score (%)"]) else None,
                        str(row["Outcome"]),
                        int(row["Response Time (hrs)"]) if not pd.isna(row["Response Time (hrs)"]) else None,
                        int(row["Compliance %"]) if not pd.isna(row["Compliance %"]) else None,
                        int(row["Doc Pages"]) if not pd.isna(row["Doc Pages"]) else None,
                        int(row["Gaps Found"]) if not pd.isna(row["Gaps Found"]) else None,
                        str(row["Bid Manager"]) if not pd.isna(row["Bid Manager"]) else None,
                        str(row["Submission Date"]) if not pd.isna(row["Submission Date"]) else None
                    ))
                print(f"Successfully seeded {len(df_history)} records into bid_history.")
            except Exception as e:
                print("Error seeding bid history:", e)
        else:
            print("dataset.xlsx not found at path:", DATASET_PATH)
            
    # 2. Seed Capability Library
    cursor.execute("SELECT COUNT(*) FROM capability_library")
    if cursor.fetchone()[0] == 0:
        if os.path.exists(DATASET_PATH):
            try:
                df_cap = pd.read_excel(DATASET_PATH, sheet_name="PS1 – Capability Library", header=2)
                df_cap = df_cap.dropna(subset=["Cap ID"])
                
                for _, row in df_cap.iterrows():
                    cap_id_str = str(row["Cap ID"])
                    domain_str = str(row["Domain"])
                    summary_str = str(row["Project Summary"])
                    cert_str = str(row["Certification"])
                    year_val = int(row["Year Completed"]) if not pd.isna(row["Year Completed"]) else None
                    value_str = str(row["Contract Value"])
                    duration_val = int(row["Duration (months)"]) if not pd.isna(row["Duration (months)"]) else None
                    client_type_str = str(row["Client Type"])

                    cursor.execute("""
                    INSERT OR REPLACE INTO capability_library 
                    (cap_id, domain, project_summary, certification, year_completed, contract_value, duration_months, client_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (cap_id_str, domain_str, summary_str, cert_str, year_val, value_str, duration_val, client_type_str))

                    # Seed the RAG capability chunks index table dynamically
                    cap_text = (
                        f"Domain: {domain_str}\n"
                        f"Project Title/Summary: {summary_str}\n"
                        f"Certification: {cert_str}\n"
                        f"Year Completed: {year_val}\n"
                        f"Contract Value: {value_str}\n"
                        f"Duration: {duration_val} months\n"
                        f"Client Type: {client_type_str}"
                    )
                    cursor.execute("""
                    INSERT OR REPLACE INTO capability_chunks (chunk_id, source_file, content, domain, metadata)
                    VALUES (?, ?, ?, ?, ?)
                    """, (
                        f"cap-seed-{cap_id_str}",
                        "dataset.xlsx",
                        cap_text,
                        domain_str,
                        f"{{\"cap_id\":\"{cap_id_str}\", \"contract_value\":\"{value_str}\", \"certification\":\"{cert_str}\"}}"
                    ))
                print(f"Successfully seeded {len(df_cap)} records into capability_library and capability_chunks.")
            except Exception as e:
                print("Error seeding capability library:", e)
                
    # 3. Seed Evaluation Criteria Taxonomy
    cursor.execute("SELECT COUNT(*) FROM evaluation_criteria")
    if cursor.fetchone()[0] == 0:
        criteria_items = [
            ("IT-01", "IT Services", "Technical Architecture Alignment", "Evaluation of software stack compatibility, API architecture, and horizontal scaling design.", "20% - 30%"),
            ("IT-02", "IT Services", "Information Security (ISO 27001)", "Assessment of data encryption at rest/transit, zero-trust policies, and valid compliance certs.", "15% - 20%"),
            ("IT-03", "IT Services", "SLA & Disaster Recovery Policies", "Review of maintenance support levels, recovery time objectives (RTO), and uptime guarantees.", "10% - 15%"),
            ("IT-04", "IT Services", "Past Performance & Scale", "Evidence of executing at least 3 similar complex software integrations in the past 5 years.", "20% - 25%"),
            ("IT-05", "IT Services", "Agile Execution & Key Personnel", "Evaluation of Scrum/Agile methodology and certifications of proposed Project Managers (PMP/CSM).", "10% - 15%"),
            
            ("CON-01", "Construction", "HSE Safety Compliance", "Evaluation of safety records, HSE policy manuals, and zero-fatality history on previous sites.", "20% - 25%"),
            ("CON-02", "Construction", "Equipment & Machinery Ownership", "Availability and age of major equipment (excavators, dump trucks, batching plants) owned/leased.", "15% - 20%"),
            ("CON-03", "Construction", "Key PE Certifications", "Quantity and licensing status of Professional Engineers (PEs) and structural consultants.", "15% - 20%"),
            ("CON-04", "Construction", "Materials Quality Assurance", "Standards for testing concrete grade strength, structural steel certifications, and raw supply lines.", "20% - 25%"),
            ("CON-05", "Construction", "CPM Timeline & Contingency", "Completeness of the Critical Path Method schedule and weather/material shortage delay contingency plans.", "10% - 15%"),
            
            ("LOG-01", "Logistics", "Fleet Capacity & GPS Standards", "Evaluation of container fleet size, fuel efficiency standards, and real-time active GPS tracking.", "20% - 25%"),
            ("LOG-02", "Logistics", "WMS Warehouse Operations", "Integration of automated Inventory tracking, barcode/RFID scanning, and cold chain capacity.", "20% - 25%"),
            ("LOG-03", "Logistics", "Customs Clearing Speed & Compliance", "Legal compliance records, customs audit history, and average import/export clearance speeds.", "15% - 20%"),
            ("LOG-04", "Logistics", "Transit SLA & On-Time Performance", "Historical metrics of on-time delivery rates, driver safety, and route optimization planning.", "15% - 20%"),
            ("LOG-05", "Logistics", "Cargo Liability Insurance Value", "Total insurance limit per shipment, claims settlement speed, and damage/theft coverage policies.", "10% - 15%")
        ]
        try:
            for item in criteria_items:
                cursor.execute("""
                INSERT OR REPLACE INTO evaluation_criteria (id, sector, criteria_name, description, weight_range)
                VALUES (?, ?, ?, ?, ?)
                """, item)
            print(f"Successfully seeded {len(criteria_items)} evaluation criteria into taxonomy.")
        except Exception as e:
            print("Error seeding evaluation criteria:", e)
            
    # 4. Seed Users
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        import json
        users_list = [
            ("admin", "Bid Manager", json.dumps(["create_workspace", "override_checklist", "edit_draft", "export_proposal"])),
            ("writer", "Pre-Sales Writer", json.dumps(["edit_draft", "export_proposal"])),
            ("viewer", "Executive Viewer", json.dumps(["export_proposal"]))
        ]
        try:
            for u in users_list:
                cursor.execute("""
                INSERT OR REPLACE INTO users (username, role, permissions)
                VALUES (?, ?, ?)
                """, u)
            print(f"Successfully seeded {len(users_list)} users.")
        except Exception as e:
            print("Error seeding users:", e)
                
    conn.commit()

if __name__ == "__main__":
    init_db()
