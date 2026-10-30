      * SYNTHETIC COPYBOOK - AP INVOICE EXTRACT (MAINFRAME AP v2.3)
       01  AP-INVOICE-REC.
           05  INV-ID          PIC X(14).
           05  VENDOR-ID       PIC X(10).
           05  INV-DATE        PIC 9(8).     *> CCYYMMDD
           05  NET-AMT         PIC 9(11)V99. *> IMPLIED DECIMAL
           05  NET-SIGN        PIC X.
           05  CURRENCY        PIC X(3).
           05  PO-REF          PIC X(12).
           05  ENTITY          PIC X(8).
