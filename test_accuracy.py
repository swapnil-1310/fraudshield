import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
os.chdir(os.path.join(os.path.dirname(__file__), 'backend'))
from core.sebi_compliance import _run_forensic_scan

tests = [
    ('CLEAR FRAUD',    'URGENT: Reliance Industries guaranteed 80% returns in 10 days! No risk. Join VIP Telegram. Pay after profit!'),
    ('LEGIT ANALYSIS', 'Infosys Q3 results show 12% revenue growth. Based on PE expansion, stock appears undervalued. Past performance is not a guarantee. Please consult a SEBI registered advisor.'),
    ('SUBTLE SCAM',    'Our research team identified breakout in ZOMATO above 180. Target: 240. Our team has 93% accuracy over 3 years. Subscribe to our premium plan for real-time alerts. Limited seats!'),
    ('STRUCTURED TIP', 'Buy HDFC Bank CMP 1650, SL 1600, Target 1750. Join our paid Telegram for daily intraday tips. 3 months subscription Rs 5000.'),
    ('BORDERLINE',     'Nifty looks bullish. Expecting 200 point move this week. Watch 17500 level closely.'),
]

for label, msg in tests:
    score, reasons, rules = _run_forensic_scan(msg)
    violations = [r for r in reasons if not r.startswith('[COMPLIANT]')]
    compliant  = [r for r in reasons if r.startswith('[COMPLIANT]')]
    verdict = 'VIOLATION' if score >= 0.6 else ('WATCH' if score >= 0.35 else 'SAFE')
    print(f'[{label}] Score: {score:.2f} | Verdict: {verdict} | Violations: {len(violations)} | Compliance: {len(compliant)}')
    for r in violations:
        print(f'   !! {r[:90]}')
    for r in compliant:
        print(f'   OK {r[:90]}')
    print()
