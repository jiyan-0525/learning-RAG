from fpdf import FPDF

SECTIONS = [
("Restarting a stuck pod",
 "When a pod enters CrashLoopBackOff, Kubernetes is deliberately waiting "
 "longer between restarts. Delete the pod with kubectl delete pod and the "
 "controller recreates it within seconds. If it returns to the same state, "
 "the fault is in the container rather than the scheduler."),
("Rotating the database password",
 "Rotate the credential in the secret store first, then update the "
 "Kubernetes secret, then restart the deployment so pods reload it. Doing "
 "these in the wrong order leaves pods holding a credential that no longer works."),
("Certificate expiry on the edge",
 "A TLS handshake failure on the public endpoint usually means the "
 "certificate expired or the chain is incomplete. Browsers cache "
 "intermediates, so a page that loads in a browser can still fail from curl."),
("Memory limits and exit code 137",
 "Exit code 137 is 128 plus signal 9, which is kill. The kernel out of "
 "memory killer stopped the process. Raise the memory limit on the "
 "deployment or find the leak."),
]

pdf = FPDF()
pdf.add_page()
pdf.set_auto_page_break(True, margin=15)

for heading, body in SECTIONS:
    pdf.set_font("helvetica", "B", 13)
    pdf.multi_cell(0, 7, heading)
    pdf.ln(1)
    pdf.set_font("helvetica", "", 11)
    pdf.multi_cell(0, 6, body)
    pdf.ln(4)

pdf.output("runbook.pdf")
print("runbook.pdf written")
