import sqlite3
import os
import uuid
import re
import json
from database import db_connect
from scoring import WinProbabilityScorer
from rag_engine import RAGEngine
import google.generativeai as genai

class ProposalWorkflowManager:
    def __init__(self):
        self.scorer = WinProbabilityScorer()
        self.rag = RAGEngine()

    def run_workflow(self, workspace_id, rfp_title, rfp_text, sector, budget_str, deadline, use_llm=False, api_key=None, llm_model="gemini-1.5-flash"):
        """
        Executes the multi-agent proposal flow:
        1. Analyst Agent: Parses RFP text to find compliance requirements and questions.
        2. Researcher Agent: Matches each extracted item against Capability Library using TF-IDF RAG.
        3. Scorer Agent: Calculates Win Probability and Go/No-Go.
        4. Writer Agent: Drafts custom technical narratives.
        5. Reviewer Agent: Audits checklist for compliance gaps.
        """
        conn = db_connect()
        cursor = conn.cursor()
        
        # Configure Gemini if requested
        gemini_active = False
        if use_llm:
            effective_key = api_key or os.environ.get("GEMINI_API_KEY")
            if effective_key:
                try:
                    genai.configure(api_key=effective_key)
                    gemini_active = True
                    print(f"Gemini LLM pipeline successfully initialized with model '{llm_model}' in run_workflow.")
                except Exception as ex:
                    print("Failed to initialize Google Generative AI, defaulting to offline templates:", ex)

        # Initialize/Update Workspace
        cursor.execute("""
        INSERT OR REPLACE INTO workspaces (id, title, client, budget, deadline, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (workspace_id, rfp_title, sector, budget_str, deadline, "Analysis"))
        conn.commit()
        
        # 1. Analyst Agent - Parse requirements and questions
        parsed = self._analyst_parse(rfp_text, use_llm=gemini_active, llm_model=llm_model)
        requirements = parsed["requirements"]
        questions = parsed["questions"]
        
        # 2. & 4. & 5. Researcher, Writer, and Reviewer Agent Loops
        gaps_count = 0
        compliance_items = []
        proposal_drafts = []
        
        # Process Compliance Requirements
        for idx, req_desc in enumerate(requirements):
            req_id = f"REQ-{idx+1:03d}"
            
            # Retrieve closest matches
            matches = self.rag.retrieve_matches(req_desc, limit=1)
            
            status = "Pass"
            evidence_str = "No suitable evidence found in the company library."
            score = 0.0
            
            if matches:
                score = matches[0]["score"]
                cap = matches[0]["capability"]
                # If match similarity is low, count as a gap
                if score < 40.0:
                    status = "Fail"
                    gaps_count += 1
                else:
                    evidence_str = f"Matched {cap['cap_id']} - {cap['project_summary']} (Value: {cap['contract_value']}, Cert: {cap['certification']})"
            else:
                status = "Fail"
                gaps_count += 1
                
            section = "Technical & Certification Requirements"
            if any(w in req_desc.lower() for w in ["sla", "kpi", "uptime", "penalty", "guarantee", "support", "service level", "credit"]):
                section = "SLA & KPI Requirements"

            compliance_items.append({
                "id": f"{workspace_id}-{req_id}",
                "workspace_id": workspace_id,
                "section": section,
                "description": req_desc,
                "is_mandatory": 1 if "must" in req_desc.lower() or "iso" in req_desc.lower() or "guarantee" in req_desc.lower() or "shall" in req_desc.lower() else 0,
                "status": status,
                "matched_evidence": evidence_str,
                "notes": f"RAG confidence match: {score}%"
            })
            
        # Process Questions & Draft Answers
        for idx, q_prompt in enumerate(questions):
            q_id = f"Q-{idx+1:02d}"
            
            # Researcher matches evidence
            matches = self.rag.retrieve_matches(q_prompt, limit=2)
            evidence_list = []
            primary_cap = None
            
            if matches:
                primary_cap = matches[0]["capability"]
                for m in matches:
                    c = m["capability"]
                    evidence_list.append(f"- Project: {c['project_summary']} (Completed: {c['year_completed']}, Domain: {c['domain']})")
            
            evidence_str = "\n".join(evidence_list) if evidence_list else "No past projects matched."
            
            # Writer Agent - Draft response
            drafted_answer = self._writer_draft(q_id, q_prompt, primary_cap, use_llm=gemini_active, llm_model=llm_model)

            
            # Reviewer Agent - Validate drafted response
            reviewer_comments = "Response draft verified against company references."
            if not primary_cap:
                reviewer_comments = "[Warning] No matching company experience found. Narrative is generic."
            elif matches[0]["score"] < 45.0:
                reviewer_comments = f"[Warning] Low capability match score ({matches[0]['score']}%). Please verify experience accuracy."
                
            proposal_drafts.append({
                "id": f"{workspace_id}-{q_id}",
                "workspace_id": workspace_id,
                "question_id": q_id,
                "question_text": q_prompt,
                "drafted_answer": drafted_answer,
                "matched_evidence": evidence_str,
                "comments": reviewer_comments
            })

        # 3. Scorer Agent - Win Probability & Go/No-Go Decision
        total_items = len(compliance_items)
        passed_items = sum(1 for item in compliance_items if item["status"] == "Pass")
        compliance_pct = (passed_items / total_items * 100) if total_items > 0 else 100
        
        scoring_res = self.scorer.calculate_score(
            sector=sector,
            budget_str=budget_str,
            compliance_pct=compliance_pct,
            gaps_count=gaps_count
        )
        
        # Save parsed data to DB
        for item in compliance_items:
            cursor.execute("""
            INSERT OR REPLACE INTO compliance_checklist (id, workspace_id, section, description, is_mandatory, status, matched_evidence, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (item["id"], item["workspace_id"], item["section"], item["description"], item["is_mandatory"], item["status"], item["matched_evidence"], item["notes"]))
            
        for draft in proposal_drafts:
            cursor.execute("""
            INSERT OR REPLACE INTO proposal_drafts (id, workspace_id, question_id, question_text, drafted_answer, matched_evidence, comments)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (draft["id"], draft["workspace_id"], draft["question_id"], draft["question_text"], draft["drafted_answer"], draft["matched_evidence"], draft["comments"]))
            
        # Update Workspace Status
        cursor.execute("UPDATE workspaces SET status = 'Drafting' WHERE id = ?", (workspace_id,))
        
        # Generate SOW Plan
        milestones, efforts, costs = self.generate_sow_plan(sector, budget_str)
        cursor.execute("""
        INSERT OR REPLACE INTO sow_plans (workspace_id, milestones, efforts, costs)
        VALUES (?, ?, ?, ?)
        """, (workspace_id, json.dumps(milestones), json.dumps(efforts), json.dumps(costs)))
        
        conn.commit()
        conn.close()
        
        return {
            "workspace_id": workspace_id,
            "win_probability": scoring_res["win_probability"],
            "decision": scoring_res["decision"],
            "scoring_breakdown": scoring_res["breakdown"],
            "gaps_found": gaps_count,
            "checklist_count": len(compliance_items),
            "questions_count": len(proposal_drafts)
        }

    def _analyst_parse(self, rfp_text, use_llm=False, llm_model="gemini-1.5-flash"):
        """
        Parses RFP text into requirements and questions.
        If use_llm is True, calls Gemini to extract structured JSON.
        Otherwise falls back to keyword heuristics.
        """
        if use_llm:
            try:
                prompt = (
                    "You are a professional proposal analyst. Analyze the following Request for Proposal (RFP) text.\n"
                    "Extract two lists in JSON format:\n"
                    "1. 'requirements': A list of all mandatory, certification, SLA, KPI, or technical specifications that a bidder must meet.\n"
                    "2. 'questions': A list of explicit questions, question prompts, or sections that the vendor is asked to describe/explain/detail in their response.\n\n"
                    "Do not include generic headings or metadata in the list. Keep extracted items concise and verbatim where possible.\n"
                    "Ensure your output is strictly a JSON object with keys 'requirements' and 'questions'. Do not output any markdown formatting or surrounding explanation, only raw JSON.\n\n"
                    f"RFP Text:\n{rfp_text}"
                )
                model = genai.GenerativeModel(llm_model)
                response = model.generate_content(prompt)
                
                # Clean up JSON if LLM returned markdown block
                clean_json_str = response.text.strip()
                if clean_json_str.startswith("```"):
                    clean_json_str = re.sub(r"^```(?:json)?", "", clean_json_str)
                    clean_json_str = re.sub(r"```$", "", clean_json_str).strip()
                
                parsed_data = json.loads(clean_json_str)
                if isinstance(parsed_data, dict) and "requirements" in parsed_data and "questions" in parsed_data:
                    return {
                        "requirements": [str(r).strip() for r in parsed_data["requirements"] if str(r).strip()],
                        "questions": [str(q).strip() for q in parsed_data["questions"] if str(q).strip()]
                    }
            except Exception as e:
                print("Gemini Analyst extraction failed, falling back to rule-based parser:", e)

        # Fallback keyword rules (the offline/offline-by-default logic)
        requirements = []
        questions = []
        
        # Split text into sentences/lines
        lines = [line.strip() for line in rfp_text.split("\n") if line.strip()]
        
        for line in lines:
            # Match questions
            if re.search(r'^(?:question|\d+\.?|q\d+\.?|describe|how|explain)\s+', line.lower()) or line.endswith("?"):
                if len(line) > 15 and line not in questions:
                    questions.append(line)
            # Match compliance clauses (including SLAs and KPIs)
            elif any(w in line.lower() for w in ["must", "shall", "require", "certification", "compliance", "iso", "sla", "kpi", "uptime", "penalty", "support", "guarantee", "service level", "credit"]):
                if len(line) > 20 and line not in requirements:
                    requirements.append(line)
                    
        # Fallbacks if parsing returned empty lists
        if not requirements:
            requirements = [
                "The vendor must possess an ISO 27001 Certification for information security.",
                "The project manager must have at least 5 years of experience in the target domain.",
                "All deliverables must be completed within the specified project timeline."
            ]
        if not questions:
            questions = [
                "Describe your company's past experience with similar technical implementations.",
                "Detail your methodology for project execution, quality assurance, and compliance checks."
            ]
            
        return {
            "requirements": requirements,
            "questions": questions
        }

    def _writer_draft(self, q_id, q_prompt, cap, use_llm=False, llm_model="gemini-1.5-flash"):
        """
        Drafts technical proposal responses citing the matched capability context.
        Uses Gemini if use_llm is True; otherwise falls back to static templates.
        """
        if use_llm:
            try:
                if not cap:
                    prompt = (
                        f"You are a professional proposal writer. Write a comprehensive response to the question: '{q_prompt}'.\n"
                        "Our organization has a long-standing history of executing complex projects in this domain. "
                        "We implement standard best practices and agile methodologies. "
                        "Since no specific project reference is matching, write a professional, high-quality, but general response "
                        "explaining our expertise, delivery framework, and risk mitigation strategies. Use Markdown formatting."
                    )
                else:
                    prompt = (
                        f"You are a professional proposal writer. Write a detailed, persuasive technical response to the question: '{q_prompt}'.\n"
                        "To prove our capability, you MUST cite and reference our matched corporate experience from this project summary:\n"
                        f"Project: {cap['project_summary']}\n"
                        f"Domain: {cap['domain']}\n"
                        f"Certification: {cap['certification']}\n"
                        f"Contract Value: {cap['contract_value']}\n"
                        f"Duration: {cap['duration_months']} months\n"
                        f"Client Type: {cap['client_type']}\n\n"
                        "Write a compelling technical response detailing how we will apply our experience, team structure, "
                        "and compliance track record to deliver on the client's goals. Incorporate bullet points and structured sections. "
                        "Format the output using standard Markdown."
                    )
                
                model = genai.GenerativeModel(llm_model)
                response = model.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                print("Gemini Writer draft generation failed, falling back to templated drafting:", e)

        # Fallback template rules (the offline/offline-by-default logic)
        if not cap:
            return (
                f"AI-Powered Draft Response for {q_id}:\n\n"
                "Our organization has a long-standing history of executing complex projects in this domain. "
                "We implement industry-standard best practices, utilize agile methodologies, and ensure all "
                "activities comply with local and international regulatory standard requirements. "
                "Our dedicated team will align directly with the client's guidelines to deliver high-quality outcomes."
            )
            
        # Synthesize custom answer referencing capability library details
        domain = cap["domain"]
        cert = cap["certification"]
        value = cap["contract_value"]
        summary = cap["project_summary"]
        duration = cap["duration_months"]
        client = cap["client_type"]
        
        cert_phrase = f" backed by our {cert} certification" if cert and cert != "N/A" else ""
        
        draft = (
            f"**Executive Proposal Response – Section {q_id}**\n\n"
            f"Our organization is uniquely positioned to address this requirement, drawing from our extensive experience "
            f"in **{domain}**{cert_phrase}. Specifically, we executed a major project in this domain: **\"{summary}\"**.\n\n"
            f"**Project Summary & Execution Strategy:**\n"
            f"- **Client Scope:** Executed for a **{client}** client, proving our capabilities in handling multi-stakeholder structures.\n"
            f"- **Scale & Duration:** The project value was **{value}** over a execution period of **{duration} months**.\n"
            f"- **Methodology:** Our team utilized standard project metrics, ensuring zero compliance slips and strict alignment "
            f"with technical mandates.\n\n"
            f"For the current project, we will deploy the same verified operational playbook and key personnel experienced in "
            f"these frameworks, minimizing risk and ensuring compliance from day one."
        )
        return draft

    def generate_sow_plan(self, sector, budget_str):
        from scoring import parse_currency
        total_budget = parse_currency(budget_str)
        if total_budget == 0.0:
            total_budget = 15_000_000.0  # default 15M PKR
            
        scale = max(0.5, min(4.0, total_budget / 20_000_000.0))
        
        if sector == "IT Services":
            efforts = [
                {"role": "Project Manager", "count": 1, "man_months": round(6 * scale, 1), "rate_per_month": "PKR 350,000", "total_cost": f"PKR {int(6 * scale * 350000):,}"},
                {"role": "Lead Software Architect", "count": 1, "man_months": round(3 * scale, 1), "rate_per_month": "PKR 500,000", "total_cost": f"PKR {int(3 * scale * 500000):,}"},
                {"role": "Senior Fullstack Developers", "count": 2, "man_months": round(12 * scale, 1), "rate_per_month": "PKR 400,000", "total_cost": f"PKR {int(12 * scale * 400000):,}"},
                {"role": "QA Automation Engineer", "count": 1, "man_months": round(4 * scale, 1), "rate_per_month": "PKR 250,000", "total_cost": f"PKR {int(4 * scale * 250000):,}"},
                {"role": "DevOps & Security Specialist", "count": 1, "man_months": round(2 * scale, 1), "rate_per_month": "PKR 450,000", "total_cost": f"PKR {int(2 * scale * 450000):,}"}
            ]
            milestones = [
                {"phase": "Phase 1: Discovery & Architecture Design", "duration": "1.5 Months", "deliverables": "SRS Document, System Architecture Diagram, API Specifications Design."},
                {"phase": "Phase 2: Core Platform Sprint Development", "duration": "3.0 Months", "deliverables": "Implemented databases, API routing layers, completed user dashboard panels."},
                {"phase": "Phase 3: Security Hardening & Integration Testing", "duration": "1.0 Month", "deliverables": "Vulnerability scans, load testing reports, ISO 27001 audit verification checkpoints."},
                {"phase": "Phase 4: UAT & Production Launch", "duration": "0.5 Months", "deliverables": "Completed user acceptance sign-off, system deployment on production cloud, final handover."}
            ]
        elif sector == "Construction":
            efforts = [
                {"role": "Project Director / Lead Engineer", "count": 1, "man_months": round(8 * scale, 1), "rate_per_month": "PKR 450,000", "total_cost": f"PKR {int(8 * scale * 450000):,}"},
                {"role": "Structural & Civil Engineers", "count": 2, "man_months": round(12 * scale, 1), "rate_per_month": "PKR 350,000", "total_cost": f"PKR {int(12 * scale * 350000):,}"},
                {"role": "HSE Safety Officer", "count": 1, "man_months": round(6 * scale, 1), "rate_per_month": "PKR 250,000", "total_cost": f"PKR {int(6 * scale * 250000):,}"},
                {"role": "Site Supervisors", "count": 2, "man_months": round(16 * scale, 1), "rate_per_month": "PKR 200,000", "total_cost": f"PKR {int(16 * scale * 200000):,}"},
                {"role": "Procurement Specialist", "count": 1, "man_months": round(4 * scale, 1), "rate_per_month": "PKR 220,000", "total_cost": f"PKR {int(4 * scale * 220000):,}"}
            ]
            milestones = [
                {"phase": "Phase 1: Site Survey & Geotechnical Engineering", "duration": "2.0 Months", "deliverables": "Soil test reports, structural concrete foundation drawings, HSE permit approvals."},
                {"phase": "Phase 2: Foundation & Concrete Reinforcement", "duration": "3.5 Months", "deliverables": "Excavation completed, concrete grade laying, steel reinforcement bars structural audit."},
                {"phase": "Phase 3: Core Structure Masonry & Framing", "duration": "4.0 Months", "deliverables": "Wall framing erection, roof installation, plumbing and electrical rough-ins."},
                {"phase": "Phase 4: Finishing Quality Checks & Handover", "duration": "1.5 Months", "deliverables": "Plastering and painting, final structural safety inspections, occupancy permit handover."}
            ]
        else:  # Logistics
            efforts = [
                {"role": "Logistics Operations Director", "count": 1, "man_months": round(5 * scale, 1), "rate_per_month": "PKR 400,000", "total_cost": f"PKR {int(5 * scale * 400000):,}"},
                {"role": "Route & Supply Chain Analysts", "count": 2, "man_months": round(10 * scale, 1), "rate_per_month": "PKR 280,000", "total_cost": f"PKR {int(10 * scale * 280000):,}"},
                {"role": "WMS Warehouse Managers", "count": 2, "man_months": round(12 * scale, 1), "rate_per_month": "PKR 250,000", "total_cost": f"PKR {int(12 * scale * 250000):,}"},
                {"role": "Compliance & Customs Officer", "count": 1, "man_months": round(4 * scale, 1), "rate_per_month": "PKR 300,000", "total_cost": f"PKR {int(4 * scale * 300000):,}"},
                {"role": "Fleet Dispatch Coordinator", "count": 1, "man_months": round(6 * scale, 1), "rate_per_month": "PKR 200,000", "total_cost": f"PKR {int(6 * scale * 200000):,}"}
            ]
            milestones = [
                {"phase": "Phase 1: Supply Chain Audit & Network Design", "duration": "1.0 Month", "deliverables": "Fleet routes latency audit, warehouse capacity mapping report, regulatory customs compliance roadmap."},
                {"phase": "Phase 2: Fleet GPS & WMS Scanner Integration", "duration": "2.5 Months", "deliverables": "WMS software active, GPS tracking systems installed on fleet, barcode reading hardware setup."},
                {"phase": "Phase 3: Logistics Hub Commissioning", "duration": "1.5 Months", "deliverables": "Staff training, dry-run fleet schedules, warehouse sorting optimization adjustments."},
                {"phase": "Phase 4: SLA Delivery Transition", "duration": "1.0 Month", "deliverables": "Live delivery tracking hand-off, operational SLA target compliance reporting, project wrap-up."}
            ]
            
        labor_cost = 0
        for eff in efforts:
            c_str = eff["total_cost"].replace("PKR", "").replace(",", "").strip()
            labor_cost += int(c_str)
            
        hardware_software = int(total_budget * 0.15)
        contingency = int(total_budget * 0.10)
        management_fee = int(total_budget - (labor_cost + hardware_software + contingency))
        
        if management_fee < 0:
            management_fee = int(total_budget * 0.12)
            total_budget = labor_cost + hardware_software + contingency + management_fee
            
        costs = [
            {"category": "Direct Personnel (Labor Effort)", "amount": f"PKR {labor_cost:,}", "percentage": f"{round(labor_cost / total_budget * 100, 1)}%"},
            {"category": "Infrastructure / Hardware & Software Licensing", "amount": f"PKR {hardware_software:,}", "percentage": f"{round(hardware_software / total_budget * 100, 1)}%"},
            {"category": "Operations Contingency & Insurance Fund", "amount": f"PKR {contingency:,}", "percentage": f"{round(contingency / total_budget * 100, 1)}%"},
            {"category": "Project Management & Admin Fee", "amount": f"PKR {management_fee:,}", "percentage": f"{round(management_fee / total_budget * 100, 1)}%"},
            {"category": "Total Project Budget Value", "amount": f"PKR {int(total_budget):,}", "percentage": "100.0%"}
        ]
        
        return milestones, efforts, costs
