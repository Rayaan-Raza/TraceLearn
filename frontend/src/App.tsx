import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Loading } from './components/PageState'
import { useAuth } from './context/AuthContext'
import { ClassProvider } from './context/ClassContext'
import { AuthPage } from './pages/Auth'
import { StudentDashboard } from './pages/student/Dashboard'
import { PracticePage } from './pages/student/Practice'
import { ProblemPage } from './pages/student/Problem'
import { ResultPage } from './pages/student/Result'
import { ProgressPage } from './pages/student/Progress'
import { StudentSubmissionsPage } from './pages/student/Submissions'
import { StudentSubmissionDetail } from './pages/student/SubmissionDetail'
import { StudentClassroomPage } from './pages/student/Classroom'
import { ClassOverview } from './pages/teacher/ClassOverview'
import { ClassroomPage } from './pages/teacher/Classroom'
import { AssignProblemPage } from './pages/teacher/AssignProblem'
import { AssignedProblemsPage } from './pages/teacher/AssignedProblems'
import { AssignedProblemDetail } from './pages/teacher/AssignedProblemDetail'
import { MisconceptionsPage } from './pages/teacher/Misconceptions'
import { StudentsPage } from './pages/teacher/Students'
import { StudentDetails } from './pages/teacher/StudentDetails'
import { SubmissionDetail } from './pages/teacher/SubmissionDetail'
import { ResearchPage } from './pages/teacher/Research'

export default function App() {
  const { user, checking } = useAuth()

  if (checking) return <Loading label="Starting TraceLearn…" />
  if (!user) return <AuthPage />

  // Routes are chosen by the role the *server* reports. This is only for
  // navigation; every API call is authorized server-side regardless.
  const home = user.role === 'teacher' ? '/teacher' : '/student'

  return (
    <ClassProvider key={user.user_id}>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to={home} replace />} />
          {user.role === 'student' ? (
            <>
              <Route path="student" element={<StudentDashboard />} />
              <Route path="student/practice" element={<PracticePage />} />
              <Route path="student/classroom" element={<StudentClassroomPage />} />
              <Route path="student/submissions" element={<StudentSubmissionsPage />} />
              <Route path="student/submissions/:submissionId" element={<StudentSubmissionDetail />} />
              <Route path="student/problem/:problemId" element={<ProblemPage />} />
              <Route path="student/result/:submissionId" element={<ResultPage />} />
              <Route path="student/progress" element={<ProgressPage />} />
            </>
          ) : (
            <>
              <Route path="teacher" element={<ClassOverview />} />
              <Route path="teacher/classroom" element={<ClassroomPage />} />
              <Route path="teacher/classroom/assign" element={<AssignProblemPage />} />
              <Route path="teacher/assigned" element={<AssignedProblemsPage />} />
              <Route path="teacher/assigned/:assignmentId" element={<AssignedProblemDetail />} />
              <Route path="teacher/misconceptions" element={<MisconceptionsPage />} />
              <Route path="teacher/misconceptions/:misconceptionId" element={<MisconceptionsPage />} />
              <Route path="teacher/students" element={<StudentsPage />} />
              <Route path="teacher/students/:studentId" element={<StudentDetails />} />
              <Route path="teacher/submission/:submissionId" element={<SubmissionDetail />} />
              <Route path="teacher/research" element={<ResearchPage />} />
            </>
          )}
          <Route path="*" element={<Navigate to={home} replace />} />
        </Route>
      </Routes>
    </ClassProvider>
  )
}
