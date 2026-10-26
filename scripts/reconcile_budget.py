"""Explicit, operator-approved ledger reconciliation. Never called by generation.

Default CLI is preview only. --apply requires an approval reference and durable
repository path. This is estimate-based risk accounting, NOT an invoice settlement.
"""
import argparse
import json
from generate_daily import Stopped, get, save, seed_pilot
from git_daily import GitStore


def reconcile(store, pilot, approval_reference, apply=False):
    if (pilot.get('model') != 'gpt-image-2.5-flare' or pilot.get('state') != 'complete'
            or pilot.get('usage') != {'input_tokens': 29, 'output_tokens': 196}
            or pilot.get('estimated_cost_usd') != 0.006025
            or pilot.get('run_id') != '40399275564'):
        raise Stopped('unsupported_pilot_cost_evidence')
    proposal = {'policy_id': 'flare-low-v1-reviewed', 'month': 'policy', 'reserved_cents': 0,
                'pilot_hold_cents': 10, 'per_call_hold_cents': 50, 'settle_success': True,
                'basis': 'Estimate only: USD .006025 x FX ceiling 2 x fees/tax factor 1.2; rounded up to AUD .10. New low 1024-square single-image calls hold AUD .50; validated successful usage settles at ceil(USD x2 FX x1.2 fees/tax x100)+1 cent, minimum 3 cents. Uncertain outcomes freeze spending.',
                'approval_reference': approval_reference}
    if not apply:
        return proposal
    if not isinstance(approval_reference, str) or not approval_reference.strip():
        raise Stopped('explicit_approval_reference_required')
    with store.locked() as db:
        seed_pilot(db, pilot)
        previous = get(db, 'budget-policy')
        if previous:
            if previous != proposal:
                raise Stopped('existing_policy_requires_separate_review')
            return previous
        record = get(db, 'pilot:2026-10-26')
        record.update(reserved_cents=10, state='pilot_estimate_reconciled',
                      original_reserved_cents=500, estimated_cost_usd=0.006025,
                      approval_reference=approval_reference, invoice_verified=False)
        # One transaction: avoid partial release without policy or provenance.
        db.save_many({'pilot:2026-10-26': record, 'budget-policy': proposal})
    return proposal


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pilot', required=True)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--approval-reference', default='')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(reconcile(GitStore(args.repo), json.loads(open(args.pilot).read()), args.approval_reference, args.apply), indent=2))
