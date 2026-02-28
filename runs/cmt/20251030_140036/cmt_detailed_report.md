# CMT Detailed Report - 20251030_140036

## Overall Performance

**Baseline**: 32.0% (50 items, 95% CI: 20.8%–45.8%)
**Syntra**: 32.0% (50 items, 95% CI: 20.8%–45.8%)

## Per-Type Performance (Syntra)

| Type | Accuracy | Correct | Total |
|------|----------|---------|-------|
| DMRG | 25.0% | 1 | 4 |
| ED | 62.5% | 5 | 8 |
| HF | 40.0% | 2 | 5 |
| Other | 25.0% | 4 | 16 |
| PEPS | 33.3% | 1 | 3 |
| QMC | 16.7% | 1 | 6 |
| SM | 33.3% | 2 | 6 |
| VMC | 0.0% | 0 | 2 |

## Example Incorrect Answers


### DMRG

**Item**: `cmt_dmrg_28`
- **Parsed**: $\boxed{b}$
- **Gold**: $\boxed{a}$
- **Response**: $\boxed{b}$...

**Item**: `cmt_dmrg_12`
- **Parsed**: $\boxed{b}$
- **Gold**: $\boxed{c;e}$
- **Response**: \boxed{b}...


### ED

**Item**: `cmt_ed_20`
- **Parsed**: $\boxed{a; c; d}$
- **Gold**: $\boxed{a; c}$
- **Response**: \boxed{a; c; d}...

**Item**: `cmt_ed_16`
- **Parsed**: $\boxed{5}$
- **Gold**: $\boxed{7}$
- **Response**: We classify by translation first: the 3×3 Brillouin zone has 9 momenta, which fall into three C4 orbits (stars): Γ (size 1), an X-type star along axes (size 4), and an M-type star at corners (size 4)....


### HF

**Item**: `cmt_hf_1`
- **Parsed**: $\boxed{\frac{1}$
- **Gold**: $\boxed{\langle c_\uparrow^\dagger(k) c_\uparrow(k) \rangle; \langle c_\downarrow^\dagger(k) c_\downarrow(k) \rangle}$
- **Response**: Translational symmetry constrains Hartree-Fock order to zero-momentum bilinears only. Thus the allowed (normal, number-conserving) order parameters are the uniform spin-density matrix elements in mome...

**Item**: `cmt_hf_0`
- **Parsed**: $\boxed{E_{\text{site}$
- **Gold**: $\boxed{U_1/2}$
- **Response**: \boxed{E_{\text{site}}=\min\!\left(3U_{1},\,2U_{1}+\frac{U_{0}}{3}\right)}...


### Other

**Item**: `cmt_other_40`
- **Parsed**: $\boxed{a;e}$
- **Gold**: $\boxed{a;d;e}$
- **Response**: \boxed{a;e}...

**Item**: `cmt_other_17`
- **Parsed**: $\boxed{\,f_{i,j,\sigma}$
- **Gold**: $\boxed{-t (p^{\dagger}_{i,\sigma}p_{j,\sigma}+p^{\dagger}_{j,\sigma}p_{i,\sigma})-U (m_{i,\uparrow}-\frac{1}{2})(m_{i,\downarrow}-\frac{1}{2})-\mu (m_{i,\uparrow}-m_{i,\downarrow}) -\mu}$
- **Response**: \boxed{\,f_{i,j,\sigma}+g_i \;=\; -\,t\left(p^{\dagger}_{i,\sigma}p_{j,\sigma}+p^{\dagger}_{j,\sigma}p_{i,\sigma}\right)\;-\;U\left(m_{i,\uparrow}-\tfrac{1}{2}\right)\left(m_{i,\downarrow}-\tfrac{1}{2...


### PEPS

**Item**: `cmt_peps_36`
- **Parsed**: $\boxed{b;c;d}$
- **Gold**: $\boxed{g}$
- **Response**: Valon-Modi synthesis:
- Valon (emotional wisdom): To honor accuracy and care, we focus on operations that directly extract universal CFT data. Thermodynamic probes like specific heat or susceptibility...

**Item**: `cmt_peps_21`
- **Parsed**: $\boxed{\,f=\frac{\partial N_k}$
- **Gold**: $\boxed{N_k B}$
- **Response**: \boxed{\,f=\frac{\partial N_k}{\partial B^{\dagger}}=\frac{\partial}{\partial B^{\dagger}}\langle \Phi(B)_k|\Phi(B)_k\rangle\,}...


### QMC

**Item**: `cmt_qmc_8`
- **Parsed**: $\boxed{b;i}$
- **Gold**: $\boxed{b;f;i}$
- **Response**: \boxed{b;i}...

**Item**: `cmt_qmc_27`
- **Parsed**: $\boxed{a;b;f;g}$
- **Gold**: $\boxed{d; g}$
- **Response**: \boxed{a;b;f;g}...


### SM

**Item**: `cmt_sm_49`
- **Parsed**: $\boxed{0.33,\,0.27}$
- **Gold**: $\boxed{0.33, 0.27}$
- **Response**: Valon-Modi synthesis:
- Valon: I want to ensure we respect the subtle boundary effects with care—the edge “defect density” should be chosen to maximize interior freedom without overconstraining the ma...

**Item**: `cmt_sm_44`
- **Parsed**: $\boxed{K_c=\sqrt{\gamma\sigma^2}$
- **Gold**: $\boxed{K_c = \sigma [1 - \frac{1}{\sqrt{3}}]\sqrt{\gamma + \frac{2\sigma^2}{3}(1 + \sqrt{1 + \frac{3\gamma}{\sigma^2}})}}$
- **Response**: \boxed{K_c=\sqrt{\gamma\sigma^2}}...


### VMC

**Item**: `cmt_vmc_6`
- **Parsed**: $\boxed{a;d;e}$
- **Gold**: $\boxed{a; b; d}$
- **Response**: \boxed{a;d;e}...

**Item**: `cmt_vmc_13`
- **Parsed**: $\boxed{c}$
- **Gold**: $\boxed{d;e}$
- **Response**: \boxed{c}...
