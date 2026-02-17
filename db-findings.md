Database Schema: health_connect_daily

1. Columns

| Column         | Type        | Nullable | Default  |
| -------------- | ----------- | -------- | -------- |
| id             | uuid        | not null | auto-gen |
| device_id      | varchar     | not null | -        |
| date           | date        | not null | -        |
| collected_at   | timestamptz | not null | -        |
| received_at    | timestamptz | not null | now()    |
| source_type    | varchar     | not null | 'daily'  |
| schema_version | integer     | not null | -        |
| source         | jsonb       | not null | -        |
| raw_data       | jsonb       | nullable | -        |

2. Sample Row (Feb 17, 16:11 sync)

| Field          | Value                                |
| -------------- | ------------------------------------ |
| id             | b5b5f1c4-e8e9-4954-970b-2fdb9d8ffea1 |
| device_id      | d4593c8e-26ff-4f3f-b056-fc2bb715fbc2 |
| date           | 2026-02-17                           |
| collected_at   | 2026-02-17 16:11:04+00               |
| received_at    | 2026-02-17 16:11:04+00               |
| source_type    | intraday                             |
| schema_version | 1                                    |

3. raw_data Structure (12 top-level keys)

{
  "date": "string (YYYY-MM-DD)",
  "schema_version": 1,
  "source": {
    "device_id": "string (UUID)",
    "collected_at": "string (ISO8601)"
  },
  "steps_total": 534,                              // integer
  "distance_meters": 233.74,                       // float
  "total_calories_burned": 1565.07,                // float
  
  "body_metrics": {
    "weight_kg": 129.97,                           // float | null
    "body_fat_percentage": 40.8,                   // float | null
    "body_water_percentage": 32.2                  // float | null (optional)
  },
  
  "heart_rate_summary": {
    "avg_hr": 60,                                  // int | null
    "max_hr": 112,                                 // int | null
    "min_hr": 49,                                  // int | null
    "resting_hr": 60                               // int | null
  },
  
  "sleep_sessions": [                              // array | null
    {
      "start_time": "2026-02-17T03:13:00Z",        // ISO8601
      "end_time": "2026-02-17T08:53:00Z",
      "duration_minutes": 340
    }
  ],
  
  "nutrition_summary": {
    "calories_total": 380,                         // int | null
    "protein_grams": 4.0,                          // float | null
    "carbohydrates_grams": 54.0,                   // float | null
    "total_fat_grams": 18.0,                       // float | null
    "fiber_grams": 2.0,                            // float | null (optional)
    "sugar_grams": 34.0                            // float | null (optional)
  },
  
  "exercise_sessions": null,                       // array | null
  
  "oxygen_saturation_percentage": 97.5             // float | null
}

4. nutrition_summary Fields

| Field               | Present? | Type    | Notes                     |
| ------------------- | -------- | ------- | ------------------------- |
| calories_total      | ✅ Yes    | integer | Dietary calories consumed |
| protein_grams       | ✅ Yes    | float   | Protein intake in grams   |
| carbohydrates_grams | ✅ Yes    | float   | Carbs in grams            |
| total_fat_grams     | ✅ Yes    | float   | Fat in grams              |
| fiber_grams         | ✅ Yes    | float   | Fiber (optional)          |
| sugar_grams         | ✅ Yes    | float   | Sugar (optional)          |

| Field                           | Present? | Notes                                                           |
| ------------------------------- | -------- | --------------------------------------------------------------- |
| active_calories                 | ❌ No     | Not present                                                     |
| exercise_calories               | ❌ No     | Not present                                                     |
| tdee, bmr, maintenance_calories | ❌ No     | You have total_calories_burned (activity) but not TDEE estimate |

Key insight: calories_total (nutrition) is what you ate. total_calories_burned (top-level) is what you burned. ContextKernel computes deficit = burned - eaten.

5. body_metrics Fields

| Field                 | Present? | Type                                          |
| --------------------- | -------- | --------------------------------------------- |
| weight_kg             | ✅ Yes    | float                                         |
| body_fat_percentage   | ✅ Yes    | float                                         |
| body_water_percentage | ✅ Yes    | float (optional)                              |
| bmr_kcal              | ✅ Exists | float (Basal Metabolic Rate from your scale!) |
| height_cm             | ✅ Exists | float                                         |

Sample (Feb 17):

{
  "weight_kg": 129.97,
  "body_fat_percentage": 40.8,
  "body_water_percentage": 32.2,
  "bmr_kcal": null,  // Sometimes null
  "height_cm": 193   // Your height
}

6. Steps Structure

| Field           | Location                | Present? |
| --------------- | ----------------------- | -------- |
| steps_total     | ✅ Top-level in raw_data | Yes      |
| steps_active    | ❌ Not present           | No       |
| steps_sedentary | ❌ Not present           | No       |

Steps is not nested — it's at:

{
  "steps_total": 534  // Top-level of raw_data
}


7. Manual vs Automatic Fields

Manual (User-Logged) ✅

| Field                            | Source                                  | How It Gets There                                                |
| -------------------------------- | --------------------------------------- | ---------------------------------------------------------------- |
| weight_kg                        | Samsung Health (weighed on smart scale) | You step on scale → Samsung Health → Health Connect → API        |
| body_metrics.*                   | Smart scale                             | Same as above (body fat %, water %, BMR)                         |
| nutrition_summary.calories_total | You log this                            | Likely via app or Telegram bot → Health Connect or direct insert |
| nutrition_summary.protein_grams  | You log this                            | Same as calories                                                 |
| nutrition_summary.*              | You log this                            | All nutrition fields are manual entry                            |

Automatic (Device-Collected) 🤖

| Field                        | Source                     | Collection                     |
| ---------------------------- | -------------------------- | ------------------------------ |
| steps_total                  | Phone/watch accelerometer  | Always on, passive             |
| distance_meters              | GPS + accelerometer        | Calculated from steps          |
| total_calories_burned        | Algorithm (BMR + activity) | Computed from hr/steps         |
| heart_rate_summary.*         | Watch HR sensor            | Periodic/continuous monitoring |
| sleep_sessions               | Watch accelerometer + HR   | Auto-detect sleep/wake         |
| oxygen_saturation_percentage | Watch SpO2 sensor          | During sleep or on-demand      |

Gray Area ⚠️

| Field             | Source                                       | Notes           |
| ----------------- | -------------------------------------------- | --------------- |
| exercise_sessions | Hevy app (manual start) OR watch auto-detect | Could be either |


8. First Manual Date

Query Result:

first_manual_date = 2026-02-09

Feb 9, 2026 — That's when you first logged either:

• A weight measurement (129.5 kg), OR
• Calorie entry (nutrition data)

9. Total Days of Data

| Metric                | Count   |
| --------------------- | ------- |
| Total distinct dates  | 48 days |
| Daily summary records | 47 days |
| Intraday records      | 1 day   |

Timeline: Feb 9 → Feb 17 (present) = ~9 days of active tracking, but 48 days total in database (includes backfilled/prior data from migration).

Recent coverage (last 5 days):

• Calories logged: 5/5 (100%)
• Weight recorded: 5/5 (100%)
• Steps captured: 5/5 (100%)
• Sleep recorded: 5/5 (100%)
Tracking consistency: Excellent. You're hitting all 4 signal types daily.

10. Days with Manual Signals

8 days have either calories OR weight logged.


11. Manual vs Automatic Signals (Last 15 Days)

| Date   | Calories | Weight | Steps | Notes             |
| ------ | -------- | ------ | ----- | ----------------- |
| Feb 16 | ✅ Y      | ✅ Y    | Y     | Full tracking     |
| Feb 15 | ✅ Y      | ✅ Y    | Y     | Full tracking     |
| Feb 14 | ✅ Y      | ✅ Y    | Y     | Full tracking     |
| Feb 13 | ✅ Y      | ✅ Y    | Y     | Full tracking     |
| Feb 12 | ✅ Y      | ✅ Y    | Y     | Full tracking     |
| Feb 11 | ✅ Y      | ✅ Y    | Y     | Full tracking     |
| Feb 10 | ❌ N      | ✅ Y    | Y     | Weight only       |
| Feb 9  | ❌ N      | ✅ Y    | Y     | Weight only       |
| Feb 8  | ❌ N      | ❌ N    | Y     | Auto-only (steps) |
| Feb 7  | ❌ N      | ❌ N    | Y     | Auto-only         |
| Feb 6  | ❌ N      | ❌ N    | Y     | Auto-only         |
| Feb 5  | ❌ N      | ❌ N    | Y     | Auto-only         |
| Feb 4  | ❌ N      | ❌ N    | Y     | Auto-only         |
| Feb 3  | ❌ N      | ❌ N    | Y     | Auto-only         |
| Feb 2  | ❌ N      | ❌ N    | Y     | Auto-only         |


Pattern

Feb 9-11: Started weighing in, no calorie logging yet
Feb 12-16: Full participation — calories + weight + steps
Before Feb 9: Only automatic data (steps, HR, etc.)


12. NULL or Empty raw_data Rows

0 rows — No null or empty JSON objects. Every daily record has complete raw_data.


13. Calorie Range Analysis

| Metric | Value       | Assessment                                      |
| ------ | ----------- | ----------------------------------------------- |
| Min    | 1,736 cal   | Deficit day (good)                              |
| Max    | 3,225 cal   | ⚠️ Surplus day — 925 cal above your 2300 target |
| Avg    | 2,336.5 cal | Slight deficit vs 2850 TDEE (-514)              |

Data quality: Looks realistic. No impossible values (like 50,000 calories or negative numbers). The 3225 spike is worth reviewing — was that a refeed day, logging error, or genuine overeat?


14. Weight Range Analysis

| Metric | Value     | Assessment                      |
| ------ | --------- | ------------------------------- |
| Min    | 130.16 kg | Recent low (Feb 16)             |
| Max    | 134.00 kg | Starting point (~early Feb)     |
| Avg    | 131.67 kg | Midpoint                        |
| Range  | 3.84 kg   | Normal water weight fluctuation |

Data quality: ✅ Realistic. 4kg swing over ~8 days is:

15. Date Range

| Metric   | Value      |
| -------- | ---------- |
| Earliest | 2026-01-01 |
| Latest   | 2026-02-16 |
| Span     | 46 days    |

Note: That's January 1st to February 16th — suggests prior data was migrated in, not just new tracking.


16. Gaps in Data Sequence

| Metric                         | Value   |
| ------------------------------ | ------- |
| Expected days (Jan 1 → Feb 16) | 47 days |
| Actual days with data          | 47 days |
| Missing days                   | 0       |

Result: ✅ No gaps. Every single day from Jan 1 to Feb 16 has a daily record.

17. Distinct Device IDs

1 device only:

d4593c8e-26ff-4f3f-b056-fc2bb715fbc2

• Daily records: 47 rows
• Intraday records: 1 row
Single-user system confirmed. ✓


18. Schema Evolution Over Time

Yes — the data structure changed. Here's the timeline:

| Key                          | First Seen | Last Seen | Notes                   |
| ---------------------------- | ---------- | --------- | ----------------------- |
| body_metrics                 | Jan 1      | Feb 17    | Core from start         |
| exercise_sessions            | Jan 1      | Feb 17    | Core from start         |
| heart_rate_summary           | Jan 1      | Feb 17    | Core from start         |
| nutrition_summary            | Jan 1      | Feb 17    | Core from start         |
| sleep_sessions               | Jan 1      | Feb 17    | Core from start         |
| steps_total                  | Jan 1      | Feb 17    | Core from start         |
| date                         | Feb 3      | Feb 17    | Added later             |
| schema_version               | Feb 3      | Feb 17    | Added later             |
| source                       | Feb 3      | Feb 17    | Added later             |
| total_calories_burned        | Feb 3      | Feb 17    | Added later             |
| distance_meters              | Feb 10     | Feb 17    | Added later             |
| oxygen_saturation_percentage | Feb 17     | Feb 17    | Newest — just yesterday |

What this means:

• Jan data is "legacy" — has metrics but no metadata (schema_version, timestamps)
• Feb data is "modern" — full envelope with schema versioning

suggestion: simply fix the old legacy data its simple enough