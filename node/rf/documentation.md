## Communication Energy Consumption Modeling

RF communication is divided into transmit, receive, and idle phases. The communication time ($T_{\mathrm{packet}}$) depends on the packet type ($k$), the data rate ($R_b$), and the total time required for communication depends on the propagation time ($\tau_p$) and transmission time ($\tau_t$). The propagation time is much smaller than the transmission time, so the time required for communication is given by equation (3).

$$
\begin{aligned}
    T &= \underbrace{\frac{k}{R_b}}_{\tau_t} + \tau_p \\
      &= \frac{k}{R_b}, \quad \tau_p \approx 0
\end{aligned}
$$

The energy consumed during RF communication depends on the MAC protocol used. The equations are shown sequentially in (4) and (5) for transmission and reception. In the idle condition, the CPU and peripherals remain active while the RF module is disabled to reduce power consumption, as shown in equation (6); the idle time \((T_{\mathrm{idle}})\) occurs when the node is neither reading sensors, transmitting, nor waiting to receive data from another node.

$$
E_\mathrm{TX} = P_{TX} \cdot T_{\mathrm{packet}}
$$

$$
E_\mathrm{RX} = P_{RX} \cdot T_{\mathrm{packet}} 
$$

$$
E_\mathrm{I} = P_{MS} \cdot T_{\mathrm{idle}} 