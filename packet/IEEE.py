"""
    The simulation is works on packet level, not bit level, and based on O-QPSK @ 2.4 GHz, 250 kbps, with parameters as follows:
    1. Symbol duration (T_s): 16 us
    2. Symbol per byte(N_s): 2 symbol/byte 

    |===================|===================|=======================|===========================|===========================|===============================|
    |Source Addr. Mode	| Dest. Addr. Mode	| PAN ID Compression	| Source PAN ID Required?	| Dest. PAN ID Required?	| Typical Use Case              |
    |===================|===================|=======================|===========================|===========================|===============================|
    |Present (≠ 0)	    | Present (≠ 0)	    |         0	            |     Yes	                | Yes	                    | Inter-PAN communication       |
    |Present (≠ 0)	    | Present (≠ 0)	    |         1	            |     No (Omits it)	        | Yes	                    | Intra-PAN communication       |
    |Present (≠ 0)	    | Absent (= 0)	    |         0	            |     Yes	                | No (Omits it)	            | Beacon, coordinator-to-device |
    |Absent (= 0)	    | Present (≠ 0)	    |         0	            |     No (Omits it)	        | Yes	                    | Device-to-coordinator         |
    |Absent (= 0)	    | Absent (= 0)	    |         0	            |     No (Omits it)	        | No (Omits it)	            | ACK frame exclusively         |
    |===================|===================|=======================|===========================|===========================|===============================|

"""
from abstract.packet import PacketModel


class IEEE_802_15_4(PacketModel):
    def __init__(
            self, 
            config
        ):
        self.packet_type        = ""
        self.sequence_number   = 0
        self.ack_flag           = False
        self.cost = 0

        """
            Default standard packet for 802.15.4
        """

        # PHY 
        self.PREAMBLE = 4
        self.SFD = 1
        self.PHY_HEADER = 1 

        # FRAME CONTROL
        # self.FRAME_TYPE                  = 3    # In bits
        # self.SECURITY_ENABLED            = 1    # In bits
        # self.FRAME_PENDING               = 1    # In bits
        # self.ACK_REQUIRED                = 1    # In bits
        # self.PAN_ID_COMPRESSION          = 1    # In bits
        # self.RESERVED                    = 3    # In bits
        # self.DESTINATION_ADDRESSING_MODE = 2    # In bits
        # self.FRAME_VERSION               = 2    # In bits
        # self.SOURCE_ADDRESSING_MODE      = 2    # In bits
        self.FRAME_CONTROL               = 2    # In bytes, total 2 bytes (16 bits)

        # MAC HEADER
        self.SEQUENCE_NUMBER             = 1
        self.DESTINATION_PAN_ID          = 2    # 0/2 bytes depend on the PAN_ID_COMPRESSION
        self.DESTINATION_ADDRESS         = 2    # 0/2/8 bytes depend on the DESTINATION_ADDRESSING_MODE
        self.SOURCE_PAN_ID               = 2    # 0/2 bytes depend on the PAN_ID_COMPRESSION
        self.SOURCE_ADDRESS              = 2    # 0/2/8 bytes depend on the DESTINATION_ADDRESSING_MODE
        self.AUXILLARY_SECURITY_HEADER   = 0    # 0/5/6/14 bytes depend on the SECURITY_ENABLED

        # Payload
        self.PAYLOAD                     = 127  # Can be 64-127 bytes depend on the FRAME_TYPE

        # MAC FOOTER
        self.CRC                         = 2

        self.packet_size                 = 0



    # This class return in packet type in bytes
    def ACK(self):
        self.packet_type        = "ACK"
        self.ack_flag           = False

        """
            This ACK packet is formed, based on the configuration of frame control as following:
            1. FRAME_TYPE = ACK
            2. SECURITY_ENABLED             = Security Disabled (No Header)
            3. FRAME_PENDING                = DISABLED 
            4. ACK_REQUIRED                 = DISABLED (Since ACK doesnt required ACK back)
            5. PAN_ID_COMPRESSION           = ENABLED (No Source PAN ID)
            6. DESTINATION_ADDRESSING_MODE  = Short Addressing (2 bytes)
            7. FRAME_VERSION                = 2003 (Since we are using 2006,
            8. SOURCE_ADDRESSING_MODE       = Short Addressing (2 bytes)

            Therefore the last MAC header is:         
            SEQUENCE_NUMBER             = 1
            DESTINATION_PAN_ID          = 0
            DESTINATION_ADDRESS         = 2
            SOURCE_PAN_ID               = 0
            SOURCE_ADDRESS              = 2
            AUXILLARY_SECURITY_HEADER   = 0

            This configuration is based on:
            https://onlinedocs.microchip.com/oxy/GUID-4B3D771E-5647-4191-AD45-C897B0D23071-en-US-3/GUID-B3E756DD-CA28-4B95-A48D-1D6E85E8A79C.html

            The ACK packet is not depend on the address, it based on sequence number. The source node (the one whom ask to send the ACK) will wait for the ACK packet with the same sequence number as the one it sent. If the ACK packet is received, it means the packet is successfully received by the destination node. If the ACK packet is not received within a certain time, it means the packet is lost and need to be retransmitted.
        """
        self.SEQUENCE_NUMBER             = 1
        self.DESTINATION_PAN_ID          = 0
        self.DESTINATION_ADDRESS         = 2
        self.SOURCE_PAN_ID               = 0
        self.SOURCE_ADDRESS              = 0
        self.AUXILLARY_SECURITY_HEADER   = 0
        self.PAYLOAD                     = 0


    
    def ADV_MSG(self):
        self.packet_type        = "ADV_MSG"
        self.ack_flag           = False

        """
            This ADV_MSG packet is formed, based on the configuration of frame control as following:
            1. FRAME_TYPE                   = ADV_MSG     
            2. SECURITY_ENABLED             = Security Disabled (No Header)
            3. FRAME_PENDING                = DISABLED 
            4. ACK_REQUIRED                 = DISABLED (Broadcast packet doesnt required ACK back)
            5. PAN_ID_COMPRESSION           = ENABLED (No Source PAN ID, but destination PAN ID must be included)
            6. DESTINATION_ADDRESSING_MODE  = Short Addressing (2 bytes)
            7. FRAME_VERSION                = 2003 (Since we are using 2006,
            8. SOURCE_ADDRESSING_MODE       = Short Addressing (2 bytes)


            Therefore the last MAC header is:         
            SEQUENCE_NUMBER             = 1
            DESTINATION_PAN_ID          = 2
            DESTINATION_ADDRESS         = 2     => Address for broadcasting 0xFFFF
            SOURCE_PAN_ID               = 0     => Omitted since PAN_ID_COMPRESSION is enabled
            SOURCE_ADDRESS              = 2
            AUXILLARY_SECURITY_HEADER   = 0

            Since this categorized as a BROADCAST packet,
        """
        self.SEQUENCE_NUMBER             = 1
        self.DESTINATION_PAN_ID          = 2
        self.DESTINATION_ADDRESS         = 2
        self.SOURCE_PAN_ID               = 0
        self.SOURCE_ADDRESS              = 2
        self.AUXILLARY_SECURITY_HEADER   = 0
        self.PAYLOAD                     = 2



    def JOIN_REQ(self):
        self.packet_type        = "JOIN_REQ"
        self.ack_flag           = False

        """
            This JOIN_REQ packet is formed, based on the configuration of frame control as following:
            1. FRAME_TYPE                   = JOIN_REQ     
            2. SECURITY_ENABLED             = Security Disabled (No Header)
            3. FRAME_PENDING                = DISABLED 
            4. ACK_REQUIRED                 = DISABLED (Since ACK doesnt required ACK back)
            5. PAN_ID_COMPRESSION           = ENABLED (No Source PAN ID, but destination PAN ID must be included)
            6. DESTINATION_ADDRESSING_MODE  = Short Addressing (2 bytes)
            7. FRAME_VERSION                = 2003 (Since we are using 2006,
            8. SOURCE_ADDRESSING_MODE       = Short Addressing (2 bytes)


            Therefore the last MAC header is:         
            SEQUENCE_NUMBER             = 1
            DESTINATION_PAN_ID          = 2
            DESTINATION_ADDRESS         = 2     => Address for the cluster head
            SOURCE_PAN_ID               = 0     => Omitted since PAN_ID_COMPRESSION is enabled
            SOURCE_ADDRESS              = 2
            AUXILLARY_SECURITY_HEADER   = 0

            Since this categorized as a BROADCAST packet,
        """
        self.SEQUENCE_NUMBER             = 1
        self.DESTINATION_PAN_ID          = 2
        self.DESTINATION_ADDRESS         = 2
        self.SOURCE_PAN_ID               = 0
        self.SOURCE_ADDRESS              = 2
        self.AUXILLARY_SECURITY_HEADER   = 0
        self.PAYLOAD                     = 2

    
    def TDMA_SCHEDULE(self):
        self.packet_type        = "TDMA_SCHEDULE"
        self.ack_flag           = True

        """
            This TDMA_SCHEDULE packet is formed, based on the configuration of frame control as following:
            1. FRAME_TYPE                   = JOIN_REQ     
            2. SECURITY_ENABLED             = Security Disabled (No Header)
            3. FRAME_PENDING                = DISABLED 
            4. ACK_REQUIRED                 = DISABLED (Since ACK doesnt required ACK back)
            5. PAN_ID_COMPRESSION           = ENABLED (No Source PAN ID, but destination PAN ID must be included)
            6. DESTINATION_ADDRESSING_MODE  = Short Addressing (2 bytes)
            7. FRAME_VERSION                = 2003 (Since we are using 2006,
            8. SOURCE_ADDRESSING_MODE       = Short Addressing (2 bytes)


            Therefore the last MAC header is:         
            SEQUENCE_NUMBER             = 1
            DESTINATION_PAN_ID          = 2
            DESTINATION_ADDRESS         = 2     => Address for the cluster head
            SOURCE_PAN_ID               = 0     => Omitted since PAN_ID_COMPRESSION is enabled
            SOURCE_ADDRESS              = 2
            AUXILLARY_SECURITY_HEADER   = 0

            Since this categorized as a BROADCAST packet,
        """
        self.SEQUENCE_NUMBER             = 1
        self.DESTINATION_PAN_ID          = 2
        self.DESTINATION_ADDRESS         = 2
        self.SOURCE_PAN_ID               = 0
        self.SOURCE_ADDRESS              = 2
        self.AUXILLARY_SECURITY_HEADER   = 0
        self.PAYLOAD                     = 4

    def SENSOR_DATA(self):
        self.packet_type        = "SENSOR_DATA"
        self.ack_flag           = False

        """
            This JOIN_REQ packet is formed, based on the configuration of frame control as following:
            1. FRAME_TYPE                   = JOIN_REQ     
            2. SECURITY_ENABLED             = Security Disabled (No Header)
            3. FRAME_PENDING                = DISABLED 
            4. ACK_REQUIRED                 = DISABLED (Since ACK doesnt required ACK back)
            5. PAN_ID_COMPRESSION           = ENABLED (No Source PAN ID, but destination PAN ID must be included)
            6. DESTINATION_ADDRESSING_MODE  = Short Addressing (2 bytes)
            7. FRAME_VERSION                = 2003 (Since we are using 2006,
            8. SOURCE_ADDRESSING_MODE       = Short Addressing (2 bytes)


            Therefore the last MAC header is:         
            SEQUENCE_NUMBER             = 1
            DESTINATION_PAN_ID          = 2
            DESTINATION_ADDRESS         = 2     => Address for the cluster head
            SOURCE_PAN_ID               = 0     => Omitted since PAN_ID_COMPRESSION is enabled
            SOURCE_ADDRESS              = 2
            AUXILLARY_SECURITY_HEADER   = 0

            Since this categorized as a BROADCAST packet,
        """
        self.SEQUENCE_NUMBER             = 1
        self.DESTINATION_PAN_ID          = 2
        self.DESTINATION_ADDRESS         = 2
        self.SOURCE_PAN_ID               = 0
        self.SOURCE_ADDRESS              = 2
        self.AUXILLARY_SECURITY_HEADER   = 0
        self.PAYLOAD                     = 6

    def SENSOR_DATA_CH(self):
        self.packet_type        = "SENSOR_DATA_CH"
        self.ack_flag           = False

        """
            This JOIN_REQ packet is formed, based on the configuration of frame control as following:
            1. FRAME_TYPE                   = JOIN_REQ     
            2. SECURITY_ENABLED             = Security Disabled (No Header)
            3. FRAME_PENDING                = DISABLED 
            4. ACK_REQUIRED                 = DISABLED (Since ACK doesnt required ACK back)
            5. PAN_ID_COMPRESSION           = ENABLED (No Source PAN ID, but destination PAN ID must be included)
            6. DESTINATION_ADDRESSING_MODE  = Short Addressing (2 bytes)
            7. FRAME_VERSION                = 2003 (Since we are using 2006,
            8. SOURCE_ADDRESSING_MODE       = Short Addressing (2 bytes)


            Therefore the last MAC header is:         
            SEQUENCE_NUMBER             = 1
            DESTINATION_PAN_ID          = 2
            DESTINATION_ADDRESS         = 2     => Address for the cluster head
            SOURCE_PAN_ID               = 0     => Omitted since PAN_ID_COMPRESSION is enabled
            SOURCE_ADDRESS              = 2
            AUXILLARY_SECURITY_HEADER   = 0

            Since this categorized as a BROADCAST packet,
        """
        self.SEQUENCE_NUMBER             = 1
        self.DESTINATION_PAN_ID          = 2
        self.DESTINATION_ADDRESS         = 2
        self.SOURCE_PAN_ID               = 0
        self.SOURCE_ADDRESS              = 2
        self.AUXILLARY_SECURITY_HEADER   = 0
        self.PAYLOAD                     = 6


    def total_bytes(self, packet_type):
        if packet_type == "SENSOR_DATA":
            self.SENSOR_DATA()
        elif packet_type == "JOIN_REQ":
            self.JOIN_REQ()
        elif packet_type == "ADV_MSG":
            self.ADV_MSG()
        elif packet_type == "ACK":
            self.ACK()
        elif packet_type == "TDMA_SCHEDULE":
            self.TDMA_SCHEDULE()

        
        return self.PREAMBLE + self.SFD + self.PHY_HEADER + self.FRAME_CONTROL + self.SEQUENCE_NUMBER + self.DESTINATION_PAN_ID + self.DESTINATION_ADDRESS + self.SOURCE_PAN_ID + self.SOURCE_ADDRESS + self.AUXILLARY_SECURITY_HEADER + self.PAYLOAD + self.CRC

    def transmit(self, transmitter, receivers, packet_type):

        self.destinations = receivers

        if packet_type == "SENSOR_DATA":
            self.SENSOR_DATA()
        elif packet_type == "JOIN_REQ":
            self.JOIN_REQ()
        elif packet_type == "ADV_MSG":
            self.ADV_MSG()
        elif packet_type == "ACK":
            self.ACK()
        elif packet_type == "TDMA_SCHEDULE":
            self.TDMA_SCHEDULE()
            self.PAYLOAD += 4 * len(self.destinations)
        elif packet_type == "SENSOR_DATA_CH":
            self.SENSOR_DATA_CH()
            self.PAYLOAD += 6 * len(self.destinations)

        self.packet_size = self.total_bytes(packet_type)
        self.sequence_number = (1 + self.sequence_number) % 256

        # print(f"""
        #     TX: {transmitter.id}
        #     RX: {receiver.id}
        #     Packet Size: {packet_size} byte
        #     seq number: {self.sequence_number}
        # """)

        return (transmitter, receivers, self.sequence_number, self.packet_size)
    
    def evaluate_sequence_number(self):
        (1 + 255) % 256

        
