from decimal import Decimal, localcontext
from pathlib import Path
import hashlib, json

D=Path('D:/Geant4/G4UniversalSim')
here=Path(__file__).parent
design=D/'docs/collab/decisions/20261105-q2-uncertainty-coverage-design-v1.json'
spec=json.loads(design.read_text(encoding='utf-8-sig'))

def distribution(n,p):
    # High-precision mode-centred recurrence. No observed simulation data.
    q=1-p; mode=int(Decimal(n+1)*p)
    weights=[Decimal(0)]*(n+1); weights[mode]=Decimal(1)
    for k in range(mode,0,-1): weights[k-1]=weights[k]*k*q/((n-k+1)*p)
    for k in range(mode,n): weights[k+1]=weights[k]*(n-k)*p/((k+1)*q)
    norm=sum(weights)
    return [w/norm for w in weights]

with localcontext() as ctx:
    ctx.prec=60
    N=2000; M=64; p=Decimal(25)/36
    # Exact integer classification of the uncorrected standard-error interval.
    covered=[k for k in range(N+1) if N*(36*k-25*N)**2 <= 4*36**2*k*(N-k)]
    assert covered==list(range(1347,1430))
    pmf=distribution(N,p); coverage=sum(pmf[k] for k in covered)
    cp=distribution(M,coverage)
    tail57=sum(cp[:57]); tail58=sum(cp[:58])
    assert tail57<Decimal('.01')<tail58
    pooled=distribution(N*M,p); cdf=Decimal(0); low=high=None
    for k,w in enumerate(pooled):
        cdf+=w
        if low is None and cdf>=Decimal('.005'): low=k
        if high is None and cdf>=Decimal('.995'): high=k; break
    assert [low,high]==[88464,89313]
    assert abs(coverage-Decimal(str(spec['single_batch_coverage_probability'])))<Decimal('1e-12')
    assert abs(tail57-Decimal(str(spec['probability_below_minimum_under_model'])))<Decimal('1e-12')
    result={'schema':'q2_finite_design_decimal_independent_v1','status':'pass','simulations_executed':0,
            'design_sha256':hashlib.sha256(design.read_bytes()).hexdigest(),
            'method':'Decimal precision60 PMF recurrence plus exact integer coverage classification',
            'single_batch_coverage_probability':str(coverage),'covered_K':[covered[0],covered[-1]],
            'P_coverage_count_lt_57':str(tail57),'P_coverage_count_lt_58':str(tail58),
            'pooled_K_central_99_percent':[low,high],
            'scope':'Preregistered binomial calculation only; no empirical coverage or physics claim.'}
    (here/'results.json').write_bytes((json.dumps(result,indent=2)+'\n').encode('utf-8'))
    print(json.dumps(result))
