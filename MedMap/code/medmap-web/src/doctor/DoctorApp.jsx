import { useDoctorSession } from './useDoctorSession.js'
import { COPY } from './copy.js'
import PatientSummarySection from './sections/PatientSummarySection.jsx'
import WorkingDiagnosisSection from './sections/WorkingDiagnosisSection.jsx'
import CandidatesSection from './sections/CandidatesSection.jsx'
import NextInformationSection from './sections/NextInformationSection.jsx'
import ComingSoonSection from './sections/ComingSoonSection.jsx'
import SessionImport from './sections/SessionImport.jsx'
import HandoffCodeImport from './sections/HandoffCodeImport.jsx'
import { userMessage } from '../api/messages.js'

// Doctor Mode(#/doctor). 환자 앱과 다른 컴포넌트·다른 데이터 계약(medmap-doctor-view-v1). 서버 저장 없음.
export default function DoctorApp({ api, handoffApi }) {
  const doctor = useDoctorSession(api ? { api } : undefined)
  const { status, view, wd, error, pending } = doctor
  const message = error ? userMessage(error) : null

  return (
    <div className="app doctor">
      <header className="app-header">
        <span className="app-header__brand">MedMap</span>
        <span>{COPY.title}</span>
      </header>
      {message && (
        <div className="notice" role="alert">
          <p className="notice__title">{message.title ?? COPY.errorTitle}</p>
          {message.body && <p className="notice__body">{message.body}</p>}
          {message.action === 'retry' && (
            <button type="button" className="button" onClick={doctor.retry} disabled={pending}>{COPY.retry}</button>
          )}
        </div>
      )}
      {status === 'loading' && <p role="status">{COPY.loading}</p>}
      {status === 'load' && (
        <>
          <HandoffCodeImport onImport={doctor.importSession} pending={pending} {...(handoffApi ? { api: handoffApi } : {})} />
          <SessionImport onImport={doctor.importSession} pending={pending} />
        </>
      )}
      {status === 'ready' && view && (
        <main className="doctor-layout">
          <div className="doctor-layout__main">
            <WorkingDiagnosisSection key={wd.state} wd={view.working_diagnosis} diagnoses={doctor.diagnoses}
              onChoose={doctor.chooseWorkingDiagnosis} pending={pending} />
            <CandidatesSection assessment={view.independent_assessment} />
            <NextInformationSection info={view.next_information} patientSaid={doctor.patientSaid}
              onAnswer={doctor.answer} pending={pending} />
          </div>
          <div className="doctor-layout__side">
            <PatientSummarySection summary={view.patient_summary} cache={doctor.cache} />
            <ComingSoonSection extensions={view.extensions} />
            <button type="button" className="button" onClick={doctor.clear} disabled={pending}>{COPY.restart}</button>
          </div>
        </main>
      )}
      <p className="doctor-notice">{COPY.prototypeNotice}</p>
    </div>
  )
}
