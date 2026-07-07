/**
 * @file payroll.js
 * @description Real-time payroll dashboard controller, tickers, sliders, and payslip generation.
 */

let payrollTickerInterval = null;
let currentPayrollMonth = new Date().toISOString().substring(0, 7); // YYYY-MM
let cachedPayrollLedger = [];
let cachedPayrollSummary = null;

/**
 * Initializes and loads the payroll ledger panel.
 */
async function loadAdminPayroll(selectedMonth = null) {
    if (selectedMonth) {
        currentPayrollMonth = selectedMonth;
    }
    
    // Set input value
    const monthInput = document.getElementById("payrollMonthFilter");
    if (monthInput) monthInput.value = currentPayrollMonth;
    
    try {
        // Fetch stats & ledger
        cachedPayrollSummary = await apiCall(`/api/payroll/summary?month=${currentPayrollMonth}&portal=elevateiq`);
        cachedPayrollLedger = await apiCall(`/api/payroll/ledger?month=${currentPayrollMonth}&portal=elevateiq`);
        
        renderPayrollSummary(cachedPayrollSummary);
        renderPayrollLedger(cachedPayrollLedger);
        startPayrollTickers(cachedPayrollSummary, cachedPayrollLedger);
    } catch (err) {
        console.error("Failed to load payroll details:", err);
    }
}

/**
 * Renders summary metrics.
 */
function renderPayrollSummary(summary) {
    document.getElementById("stat_pay_cycle").textContent = formatMonthLabel(summary.month);
    document.getElementById("stat_total_pool").textContent = formatCurrency(summary.total_monthly_payroll);
    document.getElementById("stat_burn_rate").textContent = `${formatCurrency(summary.burn_rate_sec)}/sec`;
    document.getElementById("stat_paid_amount").textContent = formatCurrency(summary.paid_amount);
    
    // Status breakdown
    const c = summary.status_counts;
    document.getElementById("stat_paid_count").textContent = c.Paid || 0;
    document.getElementById("stat_proc_count").textContent = c.Processing || 0;
    document.getElementById("stat_pend_count").textContent = c.Pending || 0;
}

/**
 * Ticks the accrued payroll and employee salaries in real time.
 */
function startPayrollTickers(summary, ledger) {
    if (payrollTickerInterval) {
        clearInterval(payrollTickerInterval);
    }
    
    const totalAccruedElem = document.getElementById("stat_total_accrued");
    const burnRate = summary.burn_rate_sec;
    const elapsedSeconds = summary.elapsed_seconds;
    const startTime = Date.now();
    
    // Month length
    const daysInMonth = getDaysInMonthString(summary.month);
    const secsInMonth = daysInMonth * 24 * 3600;
    
    payrollTickerInterval = setInterval(() => {
        const deltaSeconds = (Date.now() - startTime) / 1000;
        const totalElapsed = elapsedSeconds + deltaSeconds;
        
        // Cap elapsed at seconds in month if month is past
        const cappedElapsed = Math.min(totalElapsed, secsInMonth);
        
        // Update main accrued spend ticker
        const accruedTotal = cappedElapsed * burnRate;
        if (totalAccruedElem) {
            totalAccruedElem.innerHTML = `<span class="ticker-prefix">$</span>${accruedTotal.toLocaleString('en-US', { minimumFractionDigits: 5, maximumFractionDigits: 5 })}`;
        }
        
        // Update individual employee row tickers
        ledger.forEach(emp => {
            const empTicker = document.getElementById(`emp_ticker_${emp.employee_db_id}`);
            if (empTicker) {
                const empRate = emp.base_salary / secsInMonth;
                const empAccrued = cappedElapsed * empRate;
                empTicker.textContent = formatCurrency(empAccrued, 4);
            }
        });
    }, 100);
}

/**
 * Renders the payroll ledger table.
 */
function renderPayrollLedger(ledger) {
    const tbody = document.getElementById("payrollTableBody");
    if (!tbody) return;
    
    if (!ledger.length) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--ink-faint);">No active employees found.</td></tr>`;
        return;
    }
    
    tbody.innerHTML = ledger.map(emp => {
        const statusClass = emp.status.toLowerCase();
        const actionBtn = emp.status === 'Paid' 
            ? `<button class="btn-ghost" style="padding:4px 8px; font-size:11px;" onclick="viewPayslipModal(${JSON.stringify(emp).replace(/"/g, '&quot;')})">Payslip</button>`
            : `<button class="btn-primary" style="padding:4px 8px; font-size:11px; margin-top:0;" onclick="openPayProcessModal(${JSON.stringify(emp).replace(/"/g, '&quot;')})">Process</button>
               <button class="btn-ghost" style="padding:4px 8px; font-size:11px; margin-left:5px;" onclick="viewPayslipModal(${JSON.stringify(emp).replace(/"/g, '&quot;')})">Preview</button>`;
               
        return `
            <tr>
                <td style="font-weight:600; color:white;">${emp.employee_id}</td>
                <td>
                    <div style="font-weight:600; color:white;">${emp.name}</div>
                    <div style="font-size:10px; color:var(--ink-faint);">${emp.designation || '-'}</div>
                </td>
                <td>${emp.department || '-'}</td>
                <td style="font-weight:600;">${formatCurrency(emp.base_salary)}</td>
                <td id="emp_ticker_${emp.employee_db_id}" style="font-family:monospace; color:#00e676; font-weight:600;">$0.0000</td>
                <td><span class="badge ${statusClass}">${emp.status}</span></td>
                <td>${actionBtn}</td>
            </tr>
        `;
    }).join("");
}

/**
 * Opens individual payroll calculator modal.
 */
let selectedEmployeePay = null;
function openPayProcessModal(emp) {
    selectedEmployeePay = emp;
    
    // Set standard fields
    document.getElementById("calcEmpName").textContent = emp.name;
    document.getElementById("calcEmpId").textContent = emp.employee_id;
    document.getElementById("calcBaseSalary").value = emp.base_salary;
    
    // Set allowances
    let calc = emp.calc_details || {};
    document.getElementById("calcHra").value = (calc.hra || (emp.base_salary * 0.10)).toFixed(2);
    document.getElementById("calcDa").value = (calc.da || (emp.base_salary * 0.05)).toFixed(2);
    document.getElementById("calcMedical").value = (calc.flat || 1250.00).toFixed(2);
    document.getElementById("calcBonus").value = "0.00";
    
    // Set deductions
    document.getElementById("calcPf").value = (calc.pf || (emp.base_salary * 0.12)).toFixed(2);
    document.getElementById("calcPt").value = (calc.pt || (emp.base_salary * 0.02)).toFixed(2);
    
    // LOP proration
    const absentDays = emp.absent_days_count || 0;
    const daysInMonth = getDaysInMonthString(currentPayrollMonth);
    const calculatedLop = absentDays * (emp.base_salary / daysInMonth);
    document.getElementById("calcAbsentDays").textContent = `${absentDays} day(s) absent`;
    document.getElementById("calcLop").value = calculatedLop.toFixed(2);
    document.getElementById("calcCustomDeduction").value = "0.00";
    
    // Status
    document.getElementById("calcStatus").value = emp.status === 'Pending' ? 'Processing' : emp.status;
    
    // Calculate total net pay
    updateCalculatorTotals();
    
    // Open modal
    openModal("processPayrollModal");
}

/**
 * Dynamically updates the net pay totals inside the calculator modal.
 */
function updateCalculatorTotals() {
    const base = parseFloat(document.getElementById("calcBaseSalary").value) || 0.0;
    
    // Allowances
    const hra = parseFloat(document.getElementById("calcHra").value) || 0.0;
    const da = parseFloat(document.getElementById("calcDa").value) || 0.0;
    const med = parseFloat(document.getElementById("calcMedical").value) || 0.0;
    const bonus = parseFloat(document.getElementById("calcBonus").value) || 0.0;
    const totalAllowances = hra + da + med + bonus;
    
    // Deductions
    const pf = parseFloat(document.getElementById("calcPf").value) || 0.0;
    const pt = parseFloat(document.getElementById("calcPt").value) || 0.0;
    const lop = parseFloat(document.getElementById("calcLop").value) || 0.0;
    const customDed = parseFloat(document.getElementById("calcCustomDeduction").value) || 0.0;
    const totalDeductions = pf + pt + lop + customDed;
    
    // Net Pay
    const netPay = base + totalAllowances - totalDeductions;
    
    // Update elements
    document.getElementById("calcTotalAllowances").textContent = formatCurrency(totalAllowances);
    document.getElementById("calcTotalDeductions").textContent = formatCurrency(totalDeductions);
    document.getElementById("calcNetPay").textContent = formatCurrency(netPay);
    document.getElementById("calcNetPayRaw").value = netPay.toFixed(2);
}

/**
 * Saves/submits processed individual payroll.
 */
async function submitProcessedPayroll(event) {
    if (event) event.preventDefault();
    if (!selectedEmployeePay) return;
    
    const base = parseFloat(document.getElementById("calcBaseSalary").value) || 0.0;
    const hra = parseFloat(document.getElementById("calcHra").value) || 0.0;
    const da = parseFloat(document.getElementById("calcDa").value) || 0.0;
    const med = parseFloat(document.getElementById("calcMedical").value) || 0.0;
    const bonus = parseFloat(document.getElementById("calcBonus").value) || 0.0;
    const totalAllowances = hra + da + med + bonus;
    
    const pf = parseFloat(document.getElementById("calcPf").value) || 0.0;
    const pt = parseFloat(document.getElementById("calcPt").value) || 0.0;
    const lop = parseFloat(document.getElementById("calcLop").value) || 0.0;
    const customDed = parseFloat(document.getElementById("calcCustomDeduction").value) || 0.0;
    const totalDeductions = pf + pt + lop + customDed;
    
    const netPay = parseFloat(document.getElementById("calcNetPayRaw").value) || 0.0;
    const status = document.getElementById("calcStatus").value;
    
    try {
        const res = await apiCall("/api/payroll/process", "POST", {
            employee_db_id: selectedEmployeePay.employee_db_id,
            month: currentPayrollMonth,
            base_salary: base,
            allowances: totalAllowances,
            deductions: totalDeductions,
            net_pay: netPay,
            status: status
        });
        
        alert(res.message || "Payroll processed successfully!");
        closeModal("processPayrollModal");
        loadAdminPayroll(currentPayrollMonth);
    } catch(err) {
        console.error("Failed to save payroll run:", err);
    }
}

/**
 * Runs bulk payroll process.
 */
async function runBulkPayrun() {
    if (!confirm(`Are you sure you want to run bulk payroll for ${formatMonthLabel(currentPayrollMonth)}? This will auto-generate runs for all pending active employees.`)) {
        return;
    }
    
    try {
        const res = await apiCall("/api/payroll/bulk-process", "POST", {
            month: currentPayrollMonth,
            status: "Paid",
            portal: "elevateiq"
        });
        
        alert(res.message);
        loadAdminPayroll(currentPayrollMonth);
    } catch (err) {
        console.error("Failed to run bulk payroll:", err);
    }
}

/**
 * Views / generates a printable PDF payslip modal.
 */
function viewPayslipModal(emp) {
    const slipArea = document.getElementById("payslipPrintArea");
    if (!slipArea) return;
    
    const monthLabel = formatMonthLabel(currentPayrollMonth);
    
    // If not generated, show preview values
    const isPreview = !emp.is_generated;
    
    let allowancesBreakdown = "";
    let deductionsBreakdown = "";
    
    if (isPreview) {
        const calc = emp.calc_details || {};
        allowancesBreakdown = `
            <tr><td>Basic Salary</td><td style="text-align:right;">${formatCurrency(emp.base_salary)}</td></tr>
            <tr><td>House Rent Allowance (HRA 10%)</td><td style="text-align:right;">${formatCurrency(calc.hra || (emp.base_salary * 0.10))}</td></tr>
            <tr><td>Dearness Allowance (DA 5%)</td><td style="text-align:right;">${formatCurrency(calc.da || (emp.base_salary * 0.05))}</td></tr>
            <tr><td>Medical Allowance</td><td style="text-align:right;">${formatCurrency(calc.flat || 1250.00)}</td></tr>
        `;
        deductionsBreakdown = `
            <tr><td>Provident Fund (PF 12%)</td><td style="text-align:right;">${formatCurrency(calc.pf || (emp.base_salary * 0.12))}</td></tr>
            <tr><td>Professional Tax (PT 2%)</td><td style="text-align:right;">${formatCurrency(calc.pt || (emp.base_salary * 0.02))}</td></tr>
            <tr><td>Loss of Pay (LOP) [${emp.absent_days_count || 0} Absent Days]</td><td style="text-align:right;">${formatCurrency(calc.lop || 0.00)}</td></tr>
        `;
    } else {
        // Show actual values saved
        allowancesBreakdown = `
            <tr><td>Basic Salary</td><td style="text-align:right;">${formatCurrency(emp.base_salary)}</td></tr>
            <tr><td>Allowances & Bonuses (HRA, DA, Medical, Custom)</td><td style="text-align:right;">${formatCurrency(emp.allowances)}</td></tr>
        `;
        deductionsBreakdown = `
            <tr><td>Provident Fund, Professional Tax & LOP</td><td style="text-align:right;">${formatCurrency(emp.deductions)}</td></tr>
        `;
    }
    
    slipArea.innerHTML = `
        <div style="border: 2px solid var(--glass-border); padding: 30px; border-radius: 12px; background: rgba(12, 25, 40, 0.95); color: white; max-width: 600px; margin: auto; font-family: sans-serif;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid var(--glass-border); padding-bottom: 20px; margin-bottom: 20px;">
                <div>
                    <h2 style="margin: 0; font-size: 22px; color: var(--orange); font-weight: 700; letter-spacing: 0.5px;">ELEVATE IQ</h2>
                    <p style="margin: 3px 0 0 0; font-size: 11px; color: var(--ink-faint); text-transform: uppercase;">Corporate Salary Statement</p>
                </div>
                <div style="text-align: right;">
                    <p style="margin: 0; font-size: 13px; font-weight: 600; color: #fff;">Pay Cycle: ${monthLabel}</p>
                    <span class="badge ${emp.status.toLowerCase()}" style="display: inline-block; margin-top: 5px; font-size: 10px;">${emp.status.toUpperCase()}</span>
                </div>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; font-size: 12px; line-height: 1.5; margin-bottom: 25px; background: rgba(255,255,255,0.02); padding: 15px; border-radius: 8px; border: 1px solid var(--glass-border);">
                <div>
                    <span style="color: var(--ink-faint); text-transform: uppercase; font-size: 10px; display:block;">Employee Details</span>
                    <strong style="font-size: 14px; color:#fff; display:block; margin-top:3px;">${emp.name}</strong>
                    <span style="color:var(--ink-soft);">${emp.designation || '-'}</span><br>
                    <span style="color:var(--ink-soft);">Dept: ${emp.department || '-'}</span>
                </div>
                <div style="text-align: right;">
                    <span style="color: var(--ink-faint); text-transform: uppercase; font-size: 10px; display:block;">Employee ID</span>
                    <strong style="font-size: 14px; color:#fff; display:block; margin-top:3px;">${emp.employee_id}</strong>
                    <span style="color: var(--ink-faint); text-transform: uppercase; font-size: 10px; display:block; margin-top: 10px;">Email ID</span>
                    <span style="color:var(--ink-soft); font-family: monospace;">${emp.email}</span>
                </div>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 25px;">
                <div>
                    <h4 style="margin: 0 0 10px 0; border-bottom: 1px solid var(--glass-border); padding-bottom: 5px; color: var(--orange); font-size: 13px;">Earnings & Allowances</h4>
                    <table style="width: 100%; font-size: 11px; border-collapse: collapse;">
                        ${allowancesBreakdown}
                    </table>
                </div>
                <div>
                    <h4 style="margin: 0 0 10px 0; border-bottom: 1px solid var(--glass-border); padding-bottom: 5px; color: #ef4444; font-size: 13px;">Deductions</h4>
                    <table style="width: 100%; font-size: 11px; border-collapse: collapse;">
                        ${deductionsBreakdown}
                    </table>
                </div>
            </div>
            
            <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(0, 230, 118, 0.08); border: 1px solid rgba(0, 230, 118, 0.3); padding: 20px; border-radius: 8px; margin-bottom: 15px;">
                <div>
                    <span style="color: var(--ink-faint); font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">Net Take-Home Pay</span>
                    <div style="font-size: 26px; font-weight: 700; color: #00e676; margin-top: 4px; font-family: monospace;">${formatCurrency(emp.net_pay)}</div>
                </div>
                <div style="text-align: right; font-size: 10px; color: var(--ink-soft); max-width: 150px; line-height: 1.4;">
                    * This is a computer generated salary slip and does not require an physical signature.
                </div>
            </div>
        </div>
    `;
    
    openModal("payslipViewModal");
}

/**
 * Prints the currently displayed payslip.
 */
function printPayslip() {
    const printContent = document.getElementById("payslipPrintArea").innerHTML;
    const originalContent = document.body.innerHTML;
    
    // Simple popup print window
    const printWindow = window.open("", "_blank");
    printWindow.document.write(`
        <html>
        <head>
            <title>Payslip - ElevateIQ</title>
            <style>
                body { background: #000; color: #fff; padding: 20px; font-family: sans-serif; }
                .badge { padding: 4px 8px; border-radius: 4px; font-size: 10px; font-weight: bold; }
                .badge.paid { background: #00e676; color: #000; }
                .badge.processing { background: #ffeb3b; color: #000; }
                .badge.pending { background: #ff9100; color: #000; }
            </style>
        </head>
        <body>
            ${printContent}
            <script>window.onload = function() { window.print(); }</script>
        </body>
        </html>
    `);
    printWindow.document.close();
}

/**
 * Utility: format month string YYYY-MM to descriptive title
 */
function formatMonthLabel(monthStr) {
    if (!monthStr) return "";
    const parts = monthStr.split("-");
    const dateObj = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, 1);
    return dateObj.toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

/**
 * Utility: format currency values
 */
function formatCurrency(val, decimals = 2) {
    if (val === undefined || val === null) val = 0;
    return "$" + parseFloat(val).toLocaleString("en-US", { 
        minimumFractionDigits: decimals, 
        maximumFractionDigits: decimals 
    });
}

/**
 * Utility: get number of days in month
 */
function getDaysInMonthString(monthStr) {
    try {
        const parts = monthStr.split("-");
        return new Date(parseInt(parts[0]), parseInt(parts[1]), 0).getDate();
    } catch(e) {
        return 30;
    }
}
