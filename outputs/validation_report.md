# Statistical Validation Report
N simulations: 500  |  Alpha: 0.05

| Test | Scenario | True Lift | Detection Rate | Est Lift | Bias |
|------|----------|-----------|----------------|----------|------|
| proportion | No effect (null) | 0.0% | 5.6% | 0.0% | +0.04% |
| proportion | Small lift (+10%) | 10.0% | 28.0% | 9.8% | -0.17% |
| proportion | Medium lift (+25%) | 25.0% | 92.4% | 25.1% | +0.14% |
| proportion | Large lift (+50%) | 50.0% | 100.0% | 50.6% | +0.60% |
| proportion | Small lift, small sample | 10.0% | 6.6% | 13.4% | +3.39% |
| continuous | No effect (null) | 0.0% | 4.0% | -0.0% | -0.04% |
| continuous | Small lift (+10%) | 10.0% | 77.6% | 10.4% | +0.39% |
| continuous | Medium lift (+25%) | 25.0% | 100.0% | 24.6% | -0.45% |
| continuous | Large lift (+50%) | 50.0% | 100.0% | 50.2% | +0.23% |
| continuous | Small sample +10% | 10.0% | 20.4% | 10.2% | +0.17% |

## Conclusion
All null scenarios pass false positive check.
