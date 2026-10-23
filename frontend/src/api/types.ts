export type Role = 'student' | 'teacher'

export interface Me {
  user_id: number
  email: string
  role: Role
  student_id: number | null
  display_name: string
}

export interface ProblemSummary {
  id: string
  title: string
  function_name: string
  concept_tags: string[]
  language: 'python' | 'cpp' | string
  topic: string
  difficulty: string
  source: 'dataset' | 'custom'
}

export interface TestCasePublic {
  id: string
  name: string
  test_type: 'visible' | 'hidden' | 'diagnostic' | string
  input_json: { args?: unknown[]; stdin?: string } | null
  expected_output: unknown
}

export interface ProblemDetail extends ProblemSummary {
  slug: string
  description: string
  prerequisite_tags: string[]
  starter_code: string
  test_cases: TestCasePublic[]
}

export interface Submission {
  id: number
  student_id: number
  problem_id: string
  attempt_number: number
  source_code: string
  submitted_at: string
  execution_status: string | null
  runtime_ms: number | null
}

export interface SubmissionSummary {
  id: number
  student_id: number
  problem_id: string
  problem_title: string
  attempt_number: number
  submitted_at: string
  execution_status: string | null
  passed: boolean
  tests_passed: number
  tests_total: number
  primary_misconception: string | null
  primary_confidence: number | null
  requires_teacher_review: boolean
}

export interface TestResult {
  test_case_id: string
  passed: boolean
  test_type: string | null
  name: string | null
  actual_output_json: unknown
  expected_output_json: unknown
  error_type: string | null
  runtime_ms: number | null
}

export interface EvidenceRecordJson {
  source_type: string
  evidence_code: string
  direction: string
  weight: number
  description: string
  misconception_id: string | null
}

export interface Diagnosis {
  id: number
  mode: 'current_only' | 'history_aware'
  primary_misconception: string
  primary_confidence: number
  alternative_misconception: string | null
  alternative_confidence: number | null
  uncertainty_level: string
  requires_teacher_review: boolean
  explanation: {
    scores?: Record<string, number>
    supporting?: EvidenceRecordJson[]
    conflicting?: EvidenceRecordJson[]
  }
}

export interface RunResult {
  submission_id: number
  execution_status: string
  runtime_ms: number | null
  stderr: string
  test_results: TestResult[]
  evidence_count: number
  current_only: Diagnosis | null
  history_aware: Diagnosis | null
  hint: { level: number; text: string } | null
}

export interface EvidenceItem {
  id: number
  submission_id: number
  source_type: string
  evidence_code: string
  misconception_id: string | null
  direction: string
  weight: number
  description: string
  details_json: string
}

export interface Hint {
  level: number
  max_level: number
  text: string
  misconception_id: string
}

export interface TeacherReview {
  id: number
  submission_id: number
  diagnosis_id: number | null
  action: string
  corrected_misconception: string | null
  comment: string | null
  reviewed_at: string
}

export interface LearnerState {
  id: number
  student_id: number
  misconception_id: string
  state: string
  confidence: number
  updated_at: string
  support_count: number
  cross_problem_support_count: number
  recent_success_count: number
}

export interface LearnerProfile {
  student_id: number
  display_name: string
  is_synthetic: boolean
  learner_states: LearnerState[]
}

export interface StateTransition {
  misconception_id: string
  old_state: string
  new_state: string
  old_confidence: number
  new_confidence: number
  timestamp: string
}

export interface TimelineEntry {
  submission_id: number
  problem_id: string
  attempt_number: number
  submitted_at: string
  execution_status: string | null
  primary_diagnosis: string | null
  state_transitions: StateTransition[]
}

export interface StudentRow {
  id: number
  display_name: string
  is_synthetic: boolean
}

export interface Classroom {
  id: number
  code: string
  name: string
  teacher_name: string
  member_count: number
  join_code: string | null
  created_at: string
}

export interface Member {
  student_id: number
  display_name: string
  joined_at: string
}

export interface Assignment {
  id: number
  classroom_id: number
  classroom_name: string
  problem_id: string
  problem_title: string
  problem_topic: string
  problem_difficulty: string
  student_ids: number[]
  due_date: string
  notes: string
  state: 'active' | 'closed'
  assigned_at: string
}

export interface AssignmentDetail extends Assignment {
  results: { student_id: number; display_name: string; submissions: SubmissionSummary[] }[]
}

export interface OverviewStudentState {
  misconception_id: string
  state: string
  confidence: number
  updated_at: string
}

export interface ClassroomOverview {
  classroom: Classroom
  totals: {
    students: number
    submissions: number
    problems_completed: number
    areas_needing_attention: number
    active_assignments: number
  }
  students: {
    id: number
    display_name: string
    submission_count: number
    solved_problems: number
    latest_submitted_at: string | null
    states: OverviewStudentState[]
  }[]
  misconceptions: {
    misconception_id: string
    attention_count: number
    students: { student_id: number; display_name: string; state: string; confidence: number }[]
  }[]
}

export interface NewTestCase {
  input: string
  expected: string
  visible: boolean
}
