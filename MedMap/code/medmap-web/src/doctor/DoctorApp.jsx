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
import './doctor.css'

// 상단 오른쪽: 실제 상담 데이터가 있는 항목만(나이·성별·진단 입력 상태). 인계 번호는 가져온 뒤 보관하지 않으므로 표시하지 않는다.
function HeaderMeta({ view }) {
  const summary = view.patient_summary
  const wdState = view.working_diagnosis?.state
  return (
    <div className="doctor-header__meta" data-testid="doctor-header-meta">
      <span className="doctor-header__patient">{`${summary.age}세 · ${COPY.sex[summary.sex] ?? summary.sex}`}</span>
      {COPY.header[wdState] && (
        <span className="doctor-chip" data-state={wdState}>{COPY.header[wdState]}</span>
      )}
    </div>
  )
}

// Doctor Mode(#/doctor). 환자 앱과 다른 컴포넌트·다른 데이터 계약(medmap-doctor-view-v1). 서버 저장 없음.
export default function DoctorApp({ api, handoffApi }) {
  const doctor = useDoctorSession(api ? { api } : undefined)
  const { status, view, wd, error, pending } = doctor
  const message = error ? userMessage(error) : null

  return (
    <div className="app doctor">
      <header className="app-header doctor-header">
        <span className="doctor-header__brand">
          <span className="doctor-header__logo" aria-hidden="true" />
          <span className="app-header__brand">MedMap</span>
          <span className="doctor-header__mode">{COPY.title}</span>
        </span>
        {status === 'ready' && view && <HeaderMeta view={view} />}
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
        <div className="doctor-load">
          <HandoffCodeImport onImport={doctor.importSession} pending={pending} {...(handoffApi ? { api: handoffApi } : {})} />
          <SessionImport onImport={doctor.importSession} pending={pending} />
        </div>
      )}
      {status === 'ready' && view && (
        <>
          <main className="doctor-layout">
            <div className="doctor-layout__side">
              <PatientSummarySection summary={view.patient_summary} cache={doctor.cache} />
            </div>
            <div className="doctor-layout__main">
              <WorkingDiagnosisSection key={wd.state} wd={view.working_diagnosis} diagnoses={doctor.diagnoses}
                onChoose={doctor.chooseWorkingDiagnosis} pending={pending} />
              <CandidatesSection assessment={view.independent_assessment} />
              <NextInformationSection info={view.next_information} patientSaid={doctor.patientSaid}
                onAnswer={doctor.answer} pending={pending} />
            </div>
          </main>
          <div className="doctor-footer">
            <ComingSoonSection extensions={view.extensions} />
            <button type="button" className="button doctor-restart" onClick={doctor.clear} disabled={pending}>{COPY.restart}</button>
          </div>
        </>
      )}
      <p className="doctor-notice">{COPY.prototypeNotice}</p>
    </div>
  )
}
