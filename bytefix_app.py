import tkinter as tk
from tkinter import ttk, messagebox

try:
    import psycopg2  # type: ignore
    from psycopg2 import sql  # type: ignore
except ImportError as exc:
    raise SystemExit(
        "psycopg2 is required to run ByteFix. Install it with: pip install psycopg2-binary"
    ) from exc

# ============================================================================
# DEFAULT POSTGRESQL CONFIGURATION (Apnar local PostgreSQL info ekhane din)
# ============================================================================
DB_CONFIG = {
    "host": "localhost",
    "port": "5432",
    "dbname": "BFIX",      # Apnar database-er naam din
    "user": "postgres",        # Apnar PostgreSQL username
    "password": "1234" # Apnar PostgreSQL password
}

# ============================================================================
# SCHEMA METADATA (Matched 1:1 with the 13 Tables in the ByteFix ERD)
# ============================================================================
TABLES_META = {
    "customers": {
        "pk": "customer_id",
        "cols": ["name", "phone", "email", "address"]
    },
    "customer_devices": {
        "pk": "device_id",
        "cols": ["customer_id", "brand", "model", "serial_number", "device_type"]
    },
    "intake_tickets": {
        "pk": "ticket_id",
        "cols": ["device_id", "reported_issue", "estimated_cost", "ticket_status"]
    },
    "branches": {
        "pk": "branch_id",
        "cols": ["branch_name", "location", "phone", "manager_id"]
    },
    "employees": {
        "pk": "employee_id",
        "cols": ["branch_id", "name", "role", "email", "phone"]
    },
    "master_parts_catalog": {
        "pk": "part_id",
        "cols": ["part_name", "sku", "description", "category"]
    },
    "branch_inventory": {
        "pk": "inventory_id",
        "cols": ["branch_id", "part_id", "quantity_in_stock", "reorder_level"]
    },
    "purchase_orders": {
        "pk": "po_id",
        "cols": ["branch_id", "status", "total_amount"]
    },
    "po_items": {
        "pk": "po_item_id",
        "cols": ["po_id", "part_id", "quantity_ordered", "unit_cost"]
    },
    "repairs": {
        "pk": "repair_id",
        "cols": ["ticket_id", "employee_id", "branch_id", "repair_details", "status"]
    },
    "repair_parts_used": {
        "pk": "repair_part_id",
        "cols": ["repair_id", "inventory_id", "quantity_used", "unit_price"]
    },
    "invoices": {
        "pk": "invoice_id",
        "cols": ["repair_id", "subtotal", "tax", "total_amount", "payment_status"]
    },
    "payments": {
        "pk": "payment_id",
        "cols": ["invoice_id", "amount_paid", "payment_method", "transaction_ref"]
    }
}


class ByteFixDesktopApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ByteFix Repair & Inventory Management System (PostgreSQL)")
        self.geometry("1320x800")
        self.minsize(1100, 680)
        self.configure(bg="#0f172a")

        self.conn = None
        self.setup_styles()
        self.build_topbar()
        self.build_main_tabs()
        self.connect_db(silent=True)

    # ------------------------------------------------------------------------
    # UI STYLING
    # ------------------------------------------------------------------------
    def setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("TNotebook", background="#0f172a", borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background="#1e293b",
            foreground="#cbd5e1",
            padding=[14, 8],
            font=("Segoe UI", 10, "bold")
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#0284c7")],
            foreground=[("selected", "#ffffff")]
        )

        style.configure("Card.TFrame", background="#1e293b")
        style.configure(
            "Treeview",
            background="#ffffff",
            foreground="#0f172a",
            rowheight=25,
            fieldbackground="#ffffff",
            font=("Segoe UI", 9)
        )
        style.configure(
            "Treeview.Heading",
            background="#0284c7",
            foreground="#ffffff",
            font=("Segoe UI", 9, "bold")
        )
        style.map("Treeview", background=[("selected", "#0284c7")], foreground=[("selected", "#ffffff")])

    # ------------------------------------------------------------------------
    # TOP BAR & DATABASE CONNECTION
    # ------------------------------------------------------------------------
    def build_topbar(self):
        top = tk.Frame(self, bg="#0f172a", pady=10, padx=16)
        top.pack(fill="x")

        tk.Label(
            top,
            text="BYTEFIX REPAIR & INVENTORY SYSTEM",
            bg="#0f172a",
            fg="#38bdf8",
            font=("Segoe UI", 16, "bold")
        ).pack(side="left")

        self.status_lbl = tk.Label(
            top,
            text="● Disconnected",
            bg="#0f172a",
            fg="#ef4444",
            font=("Segoe UI", 10, "bold")
        )
        self.status_lbl.pack(side="right", padx=12)

        tk.Button(
            top,
            text="⚙ DB Settings & Connect",
            bg="#0284c7",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=12,
            pady=5,
            command=self.open_db_Modal
        ).pack(side="right", padx=6)

        tk.Button(
            top,
            text="🔓 Enable Force Delete (Cascade)",
            bg="#eab308",
            fg="#0f172a",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=12,
            pady=5,
            command=self.enable_cascade_delete
        ).pack(side="right", padx=6)

        tk.Button(
            top,
            text="↻ Refresh All Views",
            bg="#334155",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=12,
            pady=5,
            command=self.refresh_all
        ).pack(side="right", padx=6)

    def connect_db(self, silent=False):
        try:
            if self.conn:
                self.conn.close()
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.conn.autocommit = True
            self.status_lbl.config(
                text=f"● Connected ({DB_CONFIG['dbname']}@{DB_CONFIG['host']})",
                fg="#22c55e"
            )
            self.refresh_all()
            if not silent:
                messagebox.showinfo("Success", "PostgreSQL Database Connected Successfully!")
        except Exception as e:
            self.conn = None
            self.status_lbl.config(text="● Disconnected (Click DB Settings)", fg="#ef4444")
            if not silent:
                messagebox.showerror("Database Connection Error", str(e))

    def enable_cascade_delete(self):
        """Converts RESTRICT foreign keys to ON DELETE CASCADE so demo data can be deleted easily."""
        if not self.conn:
            messagebox.showwarning("Disconnected", "Connect to PostgreSQL first!")
            return
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    ALTER TABLE Customer_Devices DROP CONSTRAINT IF EXISTS customer_devices_customer_id_fkey,
                        ADD CONSTRAINT customer_devices_customer_id_fkey FOREIGN KEY (Customer_ID) REFERENCES Customers(Customer_ID) ON DELETE CASCADE;
                    ALTER TABLE Intake_Tickets DROP CONSTRAINT IF EXISTS intake_tickets_device_id_fkey,
                        ADD CONSTRAINT intake_tickets_device_id_fkey FOREIGN KEY (Device_ID) REFERENCES Customer_Devices(Device_ID) ON DELETE CASCADE;
                    ALTER TABLE Repairs DROP CONSTRAINT IF EXISTS repairs_ticket_id_fkey,
                        ADD CONSTRAINT repairs_ticket_id_fkey FOREIGN KEY (Ticket_ID) REFERENCES Intake_Tickets(Ticket_ID) ON DELETE CASCADE;
                    ALTER TABLE Invoices DROP CONSTRAINT IF EXISTS invoices_repair_id_fkey,
                        ADD CONSTRAINT invoices_repair_id_fkey FOREIGN KEY (Repair_ID) REFERENCES Repairs(Repair_ID) ON DELETE CASCADE;
                    ALTER TABLE Payments DROP CONSTRAINT IF EXISTS payments_invoice_id_fkey,
                        ADD CONSTRAINT payments_invoice_id_fkey FOREIGN KEY (Invoice_ID) REFERENCES Invoices(Invoice_ID) ON DELETE CASCADE;
                """)
            messagebox.showinfo(
                "Cascade Enabled",
                "Foreign Key constraints updated to ON DELETE CASCADE!\nNow you can delete any Customer, Device, Ticket, or Invoice without restriction errors."
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def open_db_Modal(self):
        win = tk.Toplevel(self)
        win.title("PostgreSQL Connection Settings")
        win.geometry("380x310")
        win.configure(bg="#1e293b")
        win.grab_set()

        entries = {}
        fields = [
            ("Host", "host"),
            ("Port", "port"),
            ("Database Name", "dbname"),
            ("Username", "user"),
            ("Password", "password")
        ]

        for idx, (label_text, key) in enumerate(fields):
            tk.Label(
                win, text=label_text, bg="#1e293b", fg="#e2e8f0", font=("Segoe UI", 10)
            ).grid(row=idx, column=0, padx=16, pady=10, sticky="w")

            ent = tk.Entry(
                win,
                width=25,
                font=("Segoe UI", 10),
                show="*" if key == "password" else ""
            )
            ent.insert(0, DB_CONFIG[key])
            ent.grid(row=idx, column=1, padx=10, pady=10)
            entries[key] = ent

        def save_and_connect():
            for k, ent_widget in entries.items():
                DB_CONFIG[k] = ent_widget.get().strip()
            win.destroy()
            self.connect_db(silent=False)

        tk.Button(
            win,
            text="Connect to PostgreSQL",
            bg="#22c55e",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=14,
            pady=6,
            command=save_and_connect
        ).grid(row=len(fields), column=0, columnspan=2, pady=16)

    # ------------------------------------------------------------------------
    # MAIN NOTEBOOK TABS
    # ------------------------------------------------------------------------
    def build_main_tabs(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        self.tab_dashboard = ttk.Frame(self.notebook, style="Card.TFrame")
        self.notebook.add(self.tab_dashboard, text="📊 Live Dashboard & Joined View")
        self.build_dashboard_tab()

        self.tab_workflow = ttk.Frame(self.notebook, style="Card.TFrame")
        self.notebook.add(self.tab_workflow, text="🛠 Quick Repair & Part Usage (Interactive)")
        self.build_workflow_tab()

        self.tab_crud = ttk.Frame(self.notebook, style="Card.TFrame")
        self.notebook.add(self.tab_crud, text="🗄 All 13 ERD Tables (Full CRUD)")
        self.build_crud_tab()

    # ------------------------------------------------------------------------
    # TAB 1: DASHBOARD & JOINED OPERATIONAL VIEW
    # ------------------------------------------------------------------------
    def build_dashboard_tab(self):
        kpi_frame = tk.Frame(self.tab_dashboard, bg="#1e293b", pady=12, padx=12)
        kpi_frame.pack(fill="x")

        self.kpi_labels = {}
        kpis = [
            ("customers", "Total Customers", "#0284c7"),
            ("tickets", "Active Intake Tickets", "#eab308"),
            ("repairs", "Completed Repairs", "#22c55e"),
            ("revenue", "Total Revenue (BDT)", "#8b5cf6"),
            ("low_stock", "Low Stock Alerts", "#ef4444")
        ]

        for idx, (key, title, color) in enumerate(kpis):
            card = tk.Frame(kpi_frame, bg=color, padx=16, pady=12)
            card.grid(row=0, column=idx, padx=8, sticky="nsew")
            kpi_frame.grid_columnconfigure(idx, weight=1)

            tk.Label(card, text=title, bg=color, fg="white", font=("Segoe UI", 10, "bold")).pack(anchor="w")
            val_lbl = tk.Label(card, text="0", bg=color, fg="white", font=("Segoe UI", 18, "bold"))
            val_lbl.pack(anchor="w", pady=(4, 0))
            self.kpi_labels[key] = val_lbl

        lbl_frame = tk.Frame(self.tab_dashboard, bg="#1e293b", padx=12)
        lbl_frame.pack(fill="x")
        tk.Label(
            lbl_frame,
            text="End-to-End Repair Lifecycle (Joined across Customers → Devices → Tickets → Repairs → Invoices)",
            bg="#1e293b",
            fg="#38bdf8",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=6)

        tree_frame = tk.Frame(self.tab_dashboard, bg="#1e293b", padx=12, pady=6)
        tree_frame.pack(fill="both", expand=True)

        cols = (
            "ticket_id", "customer", "phone", "device", "serial",
            "branch", "technician", "repair_status", "total_bill", "payment_status"
        )
        self.dash_tree = ttk.Treeview(tree_frame, columns=cols, show="headings")
        headers = {
            "ticket_id": "Ticket #",
            "customer": "Customer Name",
            "phone": "Phone",
            "device": "Device Model",
            "serial": "Serial No",
            "branch": "Branch",
            "technician": "Assigned Tech",
            "repair_status": "Repair Status",
            "total_bill": "Invoice Total (BDT)",
            "payment_status": "Payment Status"
        }
        for c in cols:
            self.dash_tree.heading(c, text=headers[c])
            self.dash_tree.column(c, width=115, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.dash_tree.yview)
        self.dash_tree.configure(yscrollcommand=vsb.set)
        self.dash_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def refresh_dashboard(self):
        if not self.conn:
            return
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM customers;")
                self.kpi_labels["customers"].config(text=str(cur.fetchone()[0]))

                cur.execute("SELECT COUNT(*) FROM intake_tickets WHERE ticket_status <> 'Completed';")
                self.kpi_labels["tickets"].config(text=str(cur.fetchone()[0]))

                cur.execute("SELECT COUNT(*) FROM repairs WHERE status = 'Completed';")
                self.kpi_labels["repairs"].config(text=str(cur.fetchone()[0]))

                cur.execute("SELECT COALESCE(SUM(amount_paid), 0) FROM payments;")
                rev = cur.fetchone()[0]
                self.kpi_labels["revenue"].config(text=f"৳ {rev:,.2f}")

                cur.execute("SELECT COUNT(*) FROM branch_inventory WHERE quantity_in_stock <= reorder_level;")
                self.kpi_labels["low_stock"].config(text=str(cur.fetchone()[0]))

                cur.execute("""
                    SELECT 
                        t.ticket_id,
                        c.name,
                        c.phone,
                        d.brand || ' ' || d.model AS device,
                        d.serial_number,
                        COALESCE(b.branch_name, 'Unassigned'),
                        COALESCE(e.name, 'Unassigned'),
                        COALESCE(r.status, t.ticket_status),
                        COALESCE(i.total_amount, t.estimated_cost),
                        COALESCE(i.payment_status, 'Pending Invoice')
                    FROM intake_tickets t
                    JOIN customer_devices d ON t.device_id = d.device_id
                    JOIN customers c ON d.customer_id = c.customer_id
                    LEFT JOIN repairs r ON r.ticket_id = t.ticket_id
                    LEFT JOIN branches b ON r.branch_id = b.branch_id
                    LEFT JOIN employees e ON r.employee_id = e.employee_id
                    LEFT JOIN invoices i ON i.repair_id = r.repair_id
                    ORDER BY t.ticket_id DESC;
                """)
                rows = cur.fetchall()
                self.dash_tree.delete(*self.dash_tree.get_children())
                for r in rows:
                    self.dash_tree.insert("", "end", values=r)
        except Exception as e:
            print("Dashboard refresh error:", e)

    # ------------------------------------------------------------------------
    # TAB 2: SMART WORKFLOW WITH DROPDOWNS & LIVE RESULT TABLES
    # ------------------------------------------------------------------------
    def build_workflow_tab(self):
        container = tk.Frame(self.tab_workflow, bg="#1e293b", padx=14, pady=12)
        container.pack(fill="both", expand=True)

        # ================= LEFT PANEL: SPARE PART ALLOCATION =================
        left_panel = tk.Frame(container, bg="#1e293b")
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 8))

        left_card = tk.LabelFrame(
            left_panel,
            text=" 1. Allocate Spare Part to Repair (Auto-Deducts Branch Inventory) ",
            bg="#1e293b",
            fg="#38bdf8",
            font=("Segoe UI", 10, "bold"),
            padx=14,
            pady=10
        )
        left_card.pack(fill="x")

        tk.Label(left_card, text="Select Repair Job:", bg="#1e293b", fg="#e2e8f0", font=("Segoe UI", 9)).grid(
            row=0, column=0, sticky="w", pady=6, padx=4
        )
        self.cb_repair = ttk.Combobox(left_card, state="readonly", width=42, font=("Segoe UI", 9))
        self.cb_repair.grid(row=0, column=1, pady=6, padx=4)

        tk.Label(left_card, text="Select Branch Stock Item:", bg="#1e293b", fg="#e2e8f0", font=("Segoe UI", 9)).grid(
            row=1, column=0, sticky="w", pady=6, padx=4
        )
        self.cb_inventory = ttk.Combobox(left_card, state="readonly", width=42, font=("Segoe UI", 9))
        self.cb_inventory.grid(row=1, column=1, pady=6, padx=4)

        tk.Label(left_card, text="Quantity Used:", bg="#1e293b", fg="#e2e8f0", font=("Segoe UI", 9)).grid(
            row=2, column=0, sticky="w", pady=6, padx=4
        )
        self.wf_qty = tk.Entry(left_card, width=45, font=("Segoe UI", 9))
        self.wf_qty.insert(0, "1")
        self.wf_qty.grid(row=2, column=1, pady=6, padx=4)

        tk.Label(left_card, text="Unit Price (BDT):", bg="#1e293b", fg="#e2e8f0", font=("Segoe UI", 9)).grid(
            row=3, column=0, sticky="w", pady=6, padx=4
        )
        self.wf_price = tk.Entry(left_card, width=45, font=("Segoe UI", 9))
        self.wf_price.insert(0, "3500.00")
        self.wf_price.grid(row=3, column=1, pady=6, padx=4)

        tk.Button(
            left_card,
            text="✔ Log Part & Deduct Stock Now",
            bg="#0284c7",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=14,
            pady=6,
            command=self.allocate_part_transaction
        ).grid(row=4, column=0, columnspan=2, pady=10)

        # Live Stock & Usage Preview Table on Left
        tk.Label(
            left_panel,
            text="📦 Live Branch Stock & Part Usage Log (Updates Instantly):",
            bg="#1e293b",
            fg="#38bdf8",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", pady=(10, 4))

        self.stock_tree = ttk.Treeview(
            left_panel,
            columns=("inv_id", "branch", "part_name", "stock", "reorder"),
            show="headings",
            height=10
        )
        for col, title, w in [
            ("inv_id", "Inv ID", 55),
            ("branch", "Branch Name", 140),
            ("part_name", "Spare Part Name", 190),
            ("stock", "In Stock", 75),
            ("reorder", "Reorder Lvl", 80)
        ]:
            self.stock_tree.heading(col, text=title)
            self.stock_tree.column(col, width=w, anchor="center")
        self.stock_tree.pack(fill="both", expand=True)

        # ================= RIGHT PANEL: SPLIT PAYMENT & INVOICES =================
        right_panel = tk.Frame(container, bg="#1e293b")
        right_panel.pack(side="right", fill="both", expand=True, padx=(8, 0))

        right_card = tk.LabelFrame(
            right_panel,
            text=" 2. Record Split / Installment Payment Against Invoice ",
            bg="#1e293b",
            fg="#22c55e",
            font=("Segoe UI", 10, "bold"),
            padx=14,
            pady=10
        )
        right_card.pack(fill="x")

        tk.Label(right_card, text="Select Invoice:", bg="#1e293b", fg="#e2e8f0", font=("Segoe UI", 9)).grid(
            row=0, column=0, sticky="w", pady=6, padx=4
        )
        self.cb_invoice = ttk.Combobox(right_card, state="readonly", width=42, font=("Segoe UI", 9))
        self.cb_invoice.grid(row=0, column=1, pady=6, padx=4)
        self.cb_invoice.bind("<<ComboboxSelected>>", self.on_invoice_selected)

        tk.Label(right_card, text="Amount Paid (BDT):", bg="#1e293b", fg="#e2e8f0", font=("Segoe UI", 9)).grid(
            row=1, column=0, sticky="w", pady=6, padx=4
        )
        self.pay_amount = tk.Entry(right_card, width=45, font=("Segoe UI", 9))
        self.pay_amount.grid(row=1, column=1, pady=6, padx=4)

        tk.Label(right_card, text="Payment Method:", bg="#1e293b", fg="#e2e8f0", font=("Segoe UI", 9)).grid(
            row=2, column=0, sticky="w", pady=6, padx=4
        )
        self.cb_pay_method = ttk.Combobox(
            right_card,
            values=["Cash", "Card", "Mobile_Banking"],
            state="readonly",
            width=42,
            font=("Segoe UI", 9)
        )
        self.cb_pay_method.current(2)
        self.cb_pay_method.grid(row=2, column=1, pady=6, padx=4)

        tk.Label(right_card, text="Transaction Ref:", bg="#1e293b", fg="#e2e8f0", font=("Segoe UI", 9)).grid(
            row=3, column=0, sticky="w", pady=6, padx=4
        )
        self.pay_ref = tk.Entry(right_card, width=45, font=("Segoe UI", 9))
        self.pay_ref.insert(0, "BKASH-TXN-88501")
        self.pay_ref.grid(row=3, column=1, pady=6, padx=4)

        tk.Button(
            right_card,
            text="💳 Record Payment & Sync Invoice Status",
            bg="#22c55e",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=14,
            pady=6,
            command=self.record_payment_transaction
        ).grid(row=4, column=0, columnspan=2, pady=10)

        # Live Invoice Balance & Payment Status Preview Table on Right
        tk.Label(
            right_panel,
            text="🧾 Live Invoice Balance & Payment Status (Updates Instantly):",
            bg="#1e293b",
            fg="#22c55e",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", pady=(10, 4))

        self.inv_tree = ttk.Treeview(
            right_panel,
            columns=("inv_id", "total", "paid", "due", "status"),
            show="headings",
            height=10
        )
        for col, title, w in [
            ("inv_id", "Invoice #", 70),
            ("total", "Total Bill (BDT)", 115),
            ("paid", "Total Paid (BDT)", 115),
            ("due", "Remaining Due", 115),
            ("status", "Payment Status", 115)
        ]:
            self.inv_tree.heading(col, text=title)
            self.inv_tree.column(col, width=w, anchor="center")
        self.inv_tree.pack(fill="both", expand=True)

    def refresh_workflow_tab(self):
        if not self.conn:
            return
        try:
            with self.conn.cursor() as cur:
                # 1. Populate Repair Dropdown
                cur.execute("""
                    SELECT r.repair_id, d.brand || ' ' || d.model, b.branch_name, r.status
                    FROM repairs r
                    JOIN intake_tickets t ON r.ticket_id = t.ticket_id
                    JOIN customer_devices d ON t.device_id = d.device_id
                    JOIN branches b ON r.branch_id = b.branch_id
                    ORDER BY r.repair_id ASC;
                """)
                repairs_list = [
                    f"{row[0]} | {row[1]} ({row[2]} - {row[3]})" for row in cur.fetchall()
                ]
                self.cb_repair["values"] = repairs_list
                if repairs_list and not self.cb_repair.get():
                    self.cb_repair.current(0)

                # 2. Populate Inventory Dropdown & Live Stock Tree
                cur.execute("""
                    SELECT bi.inventory_id, b.branch_name, p.part_name, bi.quantity_in_stock, bi.reorder_level
                    FROM branch_inventory bi
                    JOIN branches b ON bi.branch_id = b.branch_id
                    JOIN master_parts_catalog p ON bi.part_id = p.part_id
                    ORDER BY bi.inventory_id ASC;
                """)
                inv_rows = cur.fetchall()
                inv_list = [
                    f"{r[0]} | {r[2]} [{r[1]}] (Stock: {r[3]})" for r in inv_rows
                ]
                self.cb_inventory["values"] = inv_list
                if inv_list and not self.cb_inventory.get():
                    self.cb_inventory.current(0)

                self.stock_tree.delete(*self.stock_tree.get_children())
                for r in inv_rows:
                    self.stock_tree.insert("", "end", values=r)

                # 3. Populate Invoice Dropdown & Live Invoice Balance Tree
                cur.execute("""
                    SELECT 
                        i.invoice_id,
                        i.total_amount,
                        COALESCE(SUM(p.amount_paid), 0) AS total_paid,
                        (i.total_amount - COALESCE(SUM(p.amount_paid), 0)) AS due,
                        i.payment_status
                    FROM invoices i
                    LEFT JOIN payments p ON p.invoice_id = i.invoice_id
                    GROUP BY i.invoice_id, i.total_amount, i.payment_status
                    ORDER BY i.invoice_id ASC;
                """)
                inv_summary = cur.fetchall()
                inv_dropdown = [
                    f"{r[0]} | Bill: ৳{r[1]:,.0f} | Due: ৳{r[3]:,.0f} ({r[4]})" for r in inv_summary
                ]
                self.cb_invoice["values"] = inv_dropdown
                if inv_dropdown:
                    self.cb_invoice.current(0)
                    self.on_invoice_selected()

                self.inv_tree.delete(*self.inv_tree.get_children())
                for r in inv_summary:
                    self.inv_tree.insert(
                        "", "end",
                        values=(r[0], f"৳{r[1]:,.2f}", f"৳{r[2]:,.2f}", f"৳{r[3]:,.2f}", r[4])
                    )
        except Exception as e:
            print("Workflow refresh error:", e)

    def on_invoice_selected(self, event=None):
        val = self.cb_invoice.get()
        if not val or not self.conn:
            return
        inv_id = int(val.split("|")[0].strip())
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT i.total_amount - COALESCE(SUM(p.amount_paid), 0)
                    FROM invoices i
                    LEFT JOIN payments p ON p.invoice_id = i.invoice_id
                    WHERE i.invoice_id = %s
                    GROUP BY i.total_amount;
                """, (inv_id,))
                row = cur.fetchone()
                if row:
                    due = max(float(row[0]), 0.0)
                    self.pay_amount.delete(0, tk.END)
                    self.pay_amount.insert(0, f"{due:.2f}" if due > 0 else "500.00")
        except Exception:
            pass

    def allocate_part_transaction(self):
        if not self.conn:
            messagebox.showwarning("Disconnected", "Connect to PostgreSQL first!")
            return
        try:
            r_id = int(self.cb_repair.get().split("|")[0].strip())
            inv_id = int(self.cb_inventory.get().split("|")[0].strip())
            qty = int(self.wf_qty.get().strip())
            price = float(self.wf_price.get().strip())

            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT quantity_in_stock FROM branch_inventory WHERE inventory_id = %s;",
                    (inv_id,)
                )
                row = cur.fetchone()
                if not row:
                    messagebox.showerror("Error", f"Inventory ID {inv_id} not found!")
                    return
                if row[0] < qty:
                    messagebox.showerror("Insufficient Stock", f"Only {row[0]} units available in stock!")
                    return

                # 1. Insert part usage
                cur.execute(
                    """
                    INSERT INTO repair_parts_used (repair_id, inventory_id, quantity_used, unit_price)
                    VALUES (%s, %s, %s, %s);
                    """,
                    (r_id, inv_id, qty, price)
                )
                # 2. Deduct branch inventory stock
                cur.execute(
                    """
                    UPDATE branch_inventory
                    SET quantity_in_stock = quantity_in_stock - %s
                    WHERE inventory_id = %s;
                    """,
                    (qty, inv_id)
                )
                # 3. Also add part cost to Invoice if an invoice exists for this repair
                added_cost = qty * price
                cur.execute(
                    """
                    UPDATE invoices
                    SET subtotal = subtotal + %s,
                        total_amount = total_amount + %s,
                        payment_status = 'Partially_Paid'
                    WHERE repair_id = %s;
                    """,
                    (added_cost, added_cost, r_id)
                )

            messagebox.showinfo(
                "Part Logged & Stock Deducted",
                f"✔ Added {qty} unit(s) to Repair #{r_id}\n"
                f"✔ Deducted {qty} unit(s) from Inventory #{inv_id}\n"
                f"✔ Updated Invoice total by +৳{added_cost:,.2f}"
            )
            self.refresh_all()
        except Exception as e:
            messagebox.showerror("Transaction Error", str(e))

    def record_payment_transaction(self):
        if not self.conn:
            messagebox.showwarning("Disconnected", "Connect to PostgreSQL first!")
            return
        try:
            inv_id = int(self.cb_invoice.get().split("|")[0].strip())
            amt = float(self.pay_amount.get().strip())
            method = self.cb_pay_method.get().strip() or "Cash"
            ref = self.pay_ref.get().strip() or "MANUAL-RCPT"

            with self.conn.cursor() as cur:
                cur.execute("SELECT total_amount FROM invoices WHERE invoice_id = %s;", (inv_id,))
                inv = cur.fetchone()
                if not inv:
                    messagebox.showerror("Error", f"Invoice ID {inv_id} not found!")
                    return
                total_bill = float(inv[0])

                cur.execute(
                    """
                    INSERT INTO payments (invoice_id, amount_paid, payment_method, transaction_ref)
                    VALUES (%s, %s, %s, %s);
                    """,
                    (inv_id, amt, method, ref)
                )

                cur.execute("SELECT COALESCE(SUM(amount_paid), 0) FROM payments WHERE invoice_id = %s;", (inv_id,))
                total_paid = float(cur.fetchone()[0])

                new_status = "Paid" if total_paid >= total_bill else "Partially_Paid"
                cur.execute(
                    "UPDATE invoices SET payment_status = %s WHERE invoice_id = %s;",
                    (new_status, inv_id)
                )

            messagebox.showinfo(
                "Payment Recorded",
                f"✔ Payment of ৳{amt:,.2f} recorded for Invoice #{inv_id}!\n"
                f"✔ Total Paid: ৳{total_paid:,.2f} / ৳{total_bill:,.2f}\n"
                f"✔ New Invoice Status: {new_status}"
            )
            self.refresh_all()
        except Exception as e:
            messagebox.showerror("Payment Error", str(e))

    # ------------------------------------------------------------------------
    # TAB 3: UNIVERSAL 13-TABLE CRUD MANAGER
    # ------------------------------------------------------------------------
    def build_crud_tab(self):
        top_bar = tk.Frame(self.tab_crud, bg="#1e293b", padx=12, pady=10)
        top_bar.pack(fill="x")

        tk.Label(
            top_bar,
            text="Select ERD Table:",
            bg="#1e293b",
            fg="#38bdf8",
            font=("Segoe UI", 11, "bold")
        ).pack(side="left", padx=(0, 8))

        self.table_selector = ttk.Combobox(
            top_bar,
            values=list(TABLES_META.keys()),
            state="readonly",
            width=28,
            font=("Segoe UI", 10, "bold")
        )
        self.table_selector.current(0)
        self.table_selector.pack(side="left", padx=6)
        self.table_selector.bind("<<ComboboxSelected>>", lambda e: self.load_selected_table())

        body = tk.Frame(self.tab_crud, bg="#1e293b", padx=12, pady=6)
        body.pack(fill="both", expand=True)

        self.form_frame = tk.LabelFrame(
            body,
            text=" Record Editor ",
            bg="#1e293b",
            fg="#38bdf8",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=10
        )
        self.form_frame.pack(side="left", fill="y", padx=(0, 12))

        self.tree_container = tk.Frame(body, bg="#1e293b")
        self.tree_container.pack(side="right", fill="both", expand=True)

        self.crud_tree = ttk.Treeview(self.tree_container, show="headings")
        vsb = ttk.Scrollbar(self.tree_container, orient="vertical", command=self.crud_tree.yview)
        hsb = ttk.Scrollbar(self.tree_container, orient="horizontal", command=self.crud_tree.xview)
        self.crud_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.crud_tree.pack(side="top", fill="both", expand=True)
        hsb.pack(side="bottom", fill="x")
        vsb.pack(side="right", fill="y")

        self.crud_tree.bind("<<TreeviewSelect>>", self.on_tree_row_select)

        self.form_entries = {}
        self.selected_pk_val = None
        self.build_dynamic_form()

    def build_dynamic_form(self):
        for widget in self.form_frame.winfo_children():
            widget.destroy()
        self.form_entries.clear()
        self.selected_pk_val = None

        t_name = self.table_selector.get()
        meta = TABLES_META[t_name]

        tk.Label(
            self.form_frame,
            text=f"Table: {t_name.upper()}",
            bg="#1e293b",
            fg="#f8fafc",
            font=("Segoe UI", 10, "bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        for idx, col in enumerate(meta["cols"], start=1):
            tk.Label(
                self.form_frame,
                text=col.replace("_", " ").title() + ":",
                bg="#1e293b",
                fg="#cbd5e1",
                font=("Segoe UI", 9)
            ).grid(row=idx, column=0, sticky="w", pady=5, padx=4)

            ent = tk.Entry(self.form_frame, width=26, font=("Segoe UI", 9))
            ent.grid(row=idx, column=1, pady=5, padx=4)
            self.form_entries[col] = ent

        btn_box = tk.Frame(self.form_frame, bg="#1e293b", pady=12)
        btn_box.grid(row=len(meta["cols"]) + 1, column=0, columnspan=2)

        tk.Button(
            btn_box, text="➕ Insert", bg="#22c55e", fg="white",
            font=("Segoe UI", 9, "bold"), relief="flat", width=9, command=self.crud_insert
        ).grid(row=0, column=0, padx=4, pady=4)

        tk.Button(
            btn_box, text="✏ Update", bg="#0284c7", fg="white",
            font=("Segoe UI", 9, "bold"), relief="flat", width=9, command=self.crud_update
        ).grid(row=0, column=1, padx=4, pady=4)

        tk.Button(
            btn_box, text="🗑 Delete", bg="#ef4444", fg="white",
            font=("Segoe UI", 9, "bold"), relief="flat", width=9, command=self.crud_delete
        ).grid(row=1, column=0, padx=4, pady=4)

        tk.Button(
            btn_box, text="🧹 Clear", bg="#475569", fg="white",
            font=("Segoe UI", 9, "bold"), relief="flat", width=9, command=self.clear_form
        ).grid(row=1, column=1, padx=4, pady=4)

    def load_selected_table(self):
        self.build_dynamic_form()
        if not self.conn:
            return
        t_name = self.table_selector.get()
        pk = TABLES_META[t_name]["pk"]
        try:
            with self.conn.cursor() as cur:
                query = sql.SQL("SELECT * FROM {} ORDER BY {} ASC;").format(
                    sql.Identifier(t_name), sql.Identifier(pk)
                )
                cur.execute(query)
                rows = cur.fetchall()
                col_names = [desc[0] for desc in cur.description]

                self.crud_tree.delete(*self.crud_tree.get_children())
                self.crud_tree["columns"] = col_names
                for c in col_names:
                    self.crud_tree.heading(c, text=c.upper())
                    self.crud_tree.column(c, width=120, anchor="w")

                for r in rows:
                    self.crud_tree.insert("", "end", values=r)
        except Exception as e:
            messagebox.showerror("Query Error", str(e))

    def on_tree_row_select(self, event):
        selected = self.crud_tree.selection()
        if not selected:
            return
        values = self.crud_tree.item(selected[0], "values")
        col_names = self.crud_tree["columns"]
        row_dict = dict(zip(col_names, values))

        t_name = self.table_selector.get()
        pk_col = TABLES_META[t_name]["pk"]
        self.selected_pk_val = row_dict.get(pk_col)

        for col, ent in self.form_entries.items():
            ent.delete(0, tk.END)
            val = row_dict.get(col, "")
            if val != "None" and val is not None:
                ent.insert(0, str(val))

    def clear_form(self):
        self.selected_pk_val = None
        for ent in self.form_entries.values():
            ent.delete(0, tk.END)

    def crud_insert(self):
        if not self.conn:
            return
        t_name = self.table_selector.get()
        cols = TABLES_META[t_name]["cols"]
        vals = [self.form_entries[c].get().strip() or None for c in cols]

        try:
            with self.conn.cursor() as cur:
                query = sql.SQL("INSERT INTO {} ({}) VALUES ({});").format(
                    sql.Identifier(t_name),
                    sql.SQL(", ").join(map(sql.Identifier, cols)),
                    sql.SQL(", ").join(sql.Placeholder() * len(cols))
                )
                cur.execute(query, vals)
            messagebox.showinfo("Inserted", f"New record added to {t_name}!")
            self.refresh_all()
        except Exception as e:
            messagebox.showerror("Insert Error", str(e))

    def crud_update(self):
        if not self.conn or not self.selected_pk_val:
            messagebox.showwarning("Select Row", "Select a row from the table first!")
            return
        t_name = self.table_selector.get()
        pk_col = TABLES_META[t_name]["pk"]
        cols = TABLES_META[t_name]["cols"]
        vals = [self.form_entries[c].get().strip() or None for c in cols]
        vals.append(self.selected_pk_val)

        try:
            with self.conn.cursor() as cur:
                set_clause = sql.SQL(", ").join(
                    sql.Composed([sql.Identifier(c), sql.SQL(" = "), sql.Placeholder()]) for c in cols
                )
                query = sql.SQL("UPDATE {} SET {} WHERE {} = %s;").format(
                    sql.Identifier(t_name),
                    set_clause,
                    sql.Identifier(pk_col)
                )
                cur.execute(query, vals)
            messagebox.showinfo("Updated", f"Record {self.selected_pk_val} updated in {t_name}!")
            self.refresh_all()
        except Exception as e:
            messagebox.showerror("Update Error", str(e))

    def crud_delete(self):
        if not self.conn or not self.selected_pk_val:
            messagebox.showwarning("Select Row", "Select a row to delete first!")
            return
        t_name = self.table_selector.get()
        pk_col = TABLES_META[t_name]["pk"]

        if not messagebox.askyesno("Confirm Delete", f"Delete {pk_col} = {self.selected_pk_val} from {t_name}?"):
            return

        try:
            with self.conn.cursor() as cur:
                query = sql.SQL("DELETE FROM {} WHERE {} = %s;").format(
                    sql.Identifier(t_name), sql.Identifier(pk_col)
                )
                cur.execute(query, (self.selected_pk_val,))
            messagebox.showinfo("Deleted", "Record deleted successfully!")
            self.refresh_all()
        except Exception as e:
            messagebox.showerror(
                "Delete Restricted",
                f"{e}\n\nTip: Click the yellow '🔓 Enable Force Delete (Cascade)' button at the top bar to allow deleting linked records!"
            )

    def refresh_all(self):
        self.refresh_dashboard()
        self.refresh_workflow_tab()
        self.load_selected_table()


if __name__ == "__main__":
    app = ByteFixDesktopApp()
    app.mainloop()