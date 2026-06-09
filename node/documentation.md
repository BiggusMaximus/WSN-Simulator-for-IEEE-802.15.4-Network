## Energy Consumption Model

The energy consumption model of a sensor node consists of sensing, logging, and communication components. For the sensing and logging processes, the model proposed by Halgamuge et al. [1] is adopted. During sensing, the sensor and the MCU communicate via the I²C interface, while during logging, the MCU communicates with the memory card over the SPI interface. Both operations require only low computational power; therefore the MCU operates in Modem‑Sleep (MS) mode, in which the CPU and peripherals remain active while the RF module is disabled to reduce power consumption. The total energy consumed during the sensing period ($T_{\mathrm{sensing}}$) is given by (1), whereas the energy consumed during the logging process depends on the write and read durations, ($T_{\mathrm{write}}$) and ($T_{\mathrm{read}}$), respectively.

$$
E_\mathrm{sensing} = \left(V_s \, I_{\mathrm{sensing}} + P_\mathrm{MS}\right) \, T_\mathrm{sensing} 
$$

$$
E_\mathrm{logging} = \frac{k_d \cdot {V_s}}{8}\left( I_\mathrm{write} \cdot T_\mathrm{write} +
                        I_\mathrm{read} \cdot T_\mathrm{read} \right) + P_\mathrm{MS} \cdot \left(T_\mathrm{read} + T_\mathrm{write}\right) 
$$

### References
[1] M. N. Halgamuge, M. Zukerman, K. Ramamohanarao, and H. L. Vu, “An estimation of sensor energy consumption,” *Progress In Electromagnetics Research B*, vol. 12, pp. 259–295, 2009. doi:10.2528/PIERB08122301.