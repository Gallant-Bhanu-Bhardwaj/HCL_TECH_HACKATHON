#!/bin/bash
# Calls every endpoint once against the running server (start it first with ./run.sh mock).
# Run: ./smoke_test.sh        Reset the data afterwards with: python init_db.py
URL=http://localhost:8000
AS_OF="2026-12-03T10:00:00+05:30"
JSON="Content-Type: application/json"

echo "1. Health";             curl -s $URL/health; echo
echo "2. Train search";       curl -s -X POST $URL/chat -H "X-Passenger-Id: P007" -H "$JSON" \
  -d "{\"session_id\":\"t1\",\"message\":\"Trains from Pune to Nagpur on 5 Dec\",\"as_of\":\"$AS_OF\"}"; echo
echo "3. Refund quote";       curl -s -X POST $URL/chat -H "X-Passenger-Id: P007" -H "$JSON" \
  -d "{\"session_id\":\"t2\",\"message\":\"Refund for UR-30418?\",\"as_of\":\"$AS_OF\"}"; echo

echo "4. Cancel preview"
REPLY=$(curl -s -X POST $URL/chat -H "X-Passenger-Id: P007" -H "$JSON" \
  -d "{\"session_id\":\"t3\",\"message\":\"Cancel UR-30418\",\"as_of\":\"$AS_OF\"}")
echo "$REPLY"
ACTION=$(echo "$REPLY" | python3 -c "import sys, json; print(json.load(sys.stdin)['pending_action']['action_id'])")
TRACE=$(echo "$REPLY" | python3 -c "import sys, json; print(json.load(sys.stdin)['trace_id'])")

echo "5. Confirm (twice: the second must say 'already done')"
curl -s -X POST $URL/actions/$ACTION/confirm -H "X-Passenger-Id: P007" -H "$JSON" -d "{\"as_of\":\"$AS_OF\"}"; echo
curl -s -X POST $URL/actions/$ACTION/confirm -H "X-Passenger-Id: P007" -H "$JSON" -d "{\"as_of\":\"$AS_OF\"}"; echo

echo "6. Booking now cancelled"; curl -s $URL/bookings/UR-30418 -H "X-Passenger-Id: P007"; echo
echo "7. Someone else's booking (must be 404)"
curl -s -o /dev/null -w "%{http_code}\n" $URL/bookings/UR-48213 -H "X-Passenger-Id: P007"
echo "8. Complaint (must be handed_to_human)"; curl -s -X POST $URL/chat -H "X-Passenger-Id: P007" -H "$JSON" \
  -d "{\"session_id\":\"t4\",\"message\":\"Refund nahi mila, I want to complain\",\"as_of\":\"$AS_OF\"}"; echo
echo "9. Trace of the cancel preview"; curl -s $URL/trace/$TRACE; echo
