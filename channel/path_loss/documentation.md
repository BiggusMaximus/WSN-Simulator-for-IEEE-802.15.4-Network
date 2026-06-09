## Path Loss Modeling

We use multiple different pathloss model such as ideal channel, log-normal, egli, 3GPP-UMi, and ITU-R P1411e.g. The received power at distance \(d\) is given by (1), where \(P_{\mathrm{TX}}\) is the transmit power, \(G_{\mathrm{TX}}\) and \(G_{\mathrm{RX}}\) are the transmitter and receiver antenna gains, \(PL\) is the median path loss at distance \(d\) for a certain percentile (obtained from the ITU‑R P.1411 model), and \(X_\sigma\) is the shadowing term modeled as a zero‑mean Gaussian random variable with standard deviation \(\sigma\) (log‑normal shadowing). The fading model also add using Rician and Log-normal shadowing.


$$
P_{\mathrm{RX}}(d) = P_{\mathrm{TX}} + G_{\mathrm{TX}} + G_{\mathrm{RX}} - PL - X_{\sigma} 
$$