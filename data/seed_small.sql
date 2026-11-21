-- Small hand-written data to build and test with. P2's generated data replaces it later.

INSERT INTO stations VALUES
 ('CSMT', 'Mumbai CSMT', 'Bombay,Mumbai,CST,Bombay VT', 'Mumbai'),
 ('PUNE', 'Pune Junction', 'Pune Jn,Poona', 'Pune'),
 ('NGP',  'Nagpur', 'Nagpur Jn', 'Nagpur'),
 ('KYN',  'Kalyan', 'Kalyan Jn', 'Kalyan'),
 ('KLYI', 'Kalyani', '', 'Kalyani');

-- 12123 runs daily. 22111 leaves Mumbai at 22:00 and reaches Pune after midnight (day_offset 1).
INSERT INTO trains VALUES
 ('12123', 'Deccan Express', 'Daily', 'SL,3AC,2AC'),
 ('22111', 'Vidarbha Night Mail', 'Mon,Wed,Fri', 'SL,2AC');

INSERT INTO train_stops VALUES
 ('12123', 'CSMT', 1, NULL,    '15:00', 0),
 ('12123', 'KYN',  2, '15:50', '15:55', 0),
 ('12123', 'PUNE', 3, '18:00', '18:10', 0),
 ('12123', 'NGP',  4, '06:00', NULL,    1),
 ('22111', 'CSMT', 1, NULL,    '22:00', 0),
 ('22111', 'KYN',  2, '22:50', '22:55', 0),
 ('22111', 'PUNE', 3, '00:40', '00:50', 1),
 ('22111', 'NGP',  4, '12:00', NULL,    1);

INSERT INTO fares VALUES
 ('12123', 'SL',  'PUNE', 'NGP', 640),
 ('12123', '3AC', 'PUNE', 'NGP', 1450),
 ('12123', '2AC', 'PUNE', 'NGP', 2040),
 ('12123', '2AC', 'CSMT', 'NGP', 2450),
 ('22111', 'SL',  'PUNE', 'NGP', 610),
 ('22111', '2AC', 'PUNE', 'NGP', 1980);

INSERT INTO seats VALUES
 ('12123', '2026-12-05', 'SL',  40, 0, 0),
 ('12123', '2026-12-05', '3AC', 0,  6, 0),
 ('12123', '2026-12-05', '2AC', 5,  0, 0),
 ('22111', '2026-12-04', 'SL',  0,  0, 12),
 ('22111', '2026-12-04', '2AC', 2,  0, 0);

-- Every number here must also appear in its source document.
INSERT INTO settings VALUES
 ('cancel_charge_SL_over_48h',   60,  'RUL-CAN-01',  '2026-01-01'),
 ('cancel_charge_3AC_over_48h',  180, 'RUL-CAN-01',  '2026-01-01'),
 ('cancel_charge_2AC_over_48h',  200, 'RUL-CAN-01',  '2026-01-01'),
 ('cancel_charge_2AC_over_48h',  240, 'CIR-2026-03', '2026-12-10'),
 ('cancel_pct_12_to_48h',        25,  'RUL-CAN-01',  '2026-01-01'),
 ('cancel_pct_4_to_12h',         50,  'RUL-CAN-01',  '2026-01-01'),
 ('no_refund_under_hours',       4,   'RUL-CAN-01',  '2026-01-01'),
 ('boarding_change_cutoff_hours', 24, 'RUL-BRD-01',  '2026-01-01'),
 ('action_ttl_minutes',          10,  'RUL-GEN-01',  '2026-01-01');

-- P020 has no bookings on purpose.
INSERT INTO passengers VALUES
 ('P007', 'Asha Verma', '4821', 'en'),
 ('P012', 'Ravi Kulkarni', '7310', 'hi'),
 ('P020', 'Meera Iyer', '5502', 'en');

INSERT INTO bookings VALUES
 ('UR-30418', 'P007', '12123', '2026-12-05', 'PUNE', 'NGP', '2AC', 2040, 'CNF', '2026-11-20T10:00:00+05:30'),
 ('UR-30422', 'P007', '22111', '2026-12-04', 'PUNE', 'NGP', 'SL',  1220, 'WL',  '2026-11-20T11:00:00+05:30'),
 ('UR-48213', 'P012', '12123', '2026-12-05', 'PUNE', 'NGP', '3AC', 2900, 'RAC', '2026-11-19T09:30:00+05:30');

-- UR-30422 has one confirmed and one waitlisted traveller.
INSERT INTO booking_travellers VALUES
 ('UR-30418', 'Asha Verma',   34, 'CNF', 'A1', '12'),
 ('UR-30422', 'Asha Verma',   34, 'CNF', 'S4', '33'),
 ('UR-30422', 'Rohan Verma',  8,  'WL',  NULL, NULL),
 ('UR-48213', 'Ravi Kulkarni', 41, 'RAC', 'B2', '7'),
 ('UR-48213', 'Sunita Kulkarni', 39, 'RAC', 'B2', '7');
