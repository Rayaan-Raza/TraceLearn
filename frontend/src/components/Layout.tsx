import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth, useMe } from '../context/AuthContext'
import { useClasses } from '../context/ClassContext'

const studentLinks = [
  { to: '/student', end: true, label: 'Dashboard' },
  { to: '/student/practice', label: 'Practice' },
  { to: '/student/classroom', label: 'Classroom' },
  { to: '/student/submissions', label: 'Submissions' },
  { to: '/student/progress', label: 'Progress' },
]

const teacherLinks = [
  { to: '/teacher', end: true, label: 'Class Overview' },
  { to: '/teacher/classroom', label: 'Classroom' },
  { to: '/teacher/assigned', label: 'Assigned Problems' },
  { to: '/teacher/misconceptions', label: 'Misconceptions' },
  { to: '/teacher/students', label: 'Students' },
  { to: '/teacher/research', label: 'Research' },
]

export function Layout() {
  const me = useMe()
  const { logout } = useAuth()
  const { classrooms, current, setCurrentId } = useClasses()
  const navigate = useNavigate()
  const role = me.role
  const links = role === 'student' ? studentLinks : teacherLinks

  async function signOut() {
    await logout()
    navigate('/', { replace: true })
  }

  return (
    <div className={`app-shell ${role}`}>
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">TraceLearn</div>
          <div className="brand-sub">Learning patterns, made visible</div>
        </div>

        {role === 'teacher' && classrooms.length > 1 ? (
          <label className="class-switch">
            <span>Classroom</span>
            <select value={current?.id ?? ''} onChange={(e) => setCurrentId(Number(e.target.value))}>
              {classrooms.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.code} — {c.name}
                </option>
              ))}
            </select>
          </label>
        ) : null}

        <nav className="nav">
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.end} className={({ isActive }) => (isActive ? 'active' : undefined)}>
              {link.label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          {current ? (
            <>
              {current.code} — {current.name}
              <br />
            </>
          ) : null}
          Signed in as {me.display_name || me.email}
          <br />
          <button type="button" className="signout" onClick={() => void signOut()}>
            Sign out
          </button>
        </div>
      </aside>

      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
