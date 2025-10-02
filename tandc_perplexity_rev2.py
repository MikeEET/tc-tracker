"""
Testing and Commissioning (T&C) Tracker Application with Data Entry
Supports Desktop and Mobile (via browser)
Built with Streamlit for cross-platform compatibility
Allows editing statuses, adding outstanding items, and tracking deficiencies
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import io

# Page configuration
st.set_page_config(
    page_title="T&C Tracker",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .status-complete { color: #22c55e; font-weight: bold; }
    .status-progress { color: #f59e0b; font-weight: bold; }
    .status-open { color: #ef4444; font-weight: bold; }
    .status-na { color: #6b7280; font-weight: bold; }
    .deficiency-box {
        background-color: #fef2f2;
        border-left: 4px solid #ef4444;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    @media (max-width: 768px) {
        .main-header { font-size: 1.8rem; }
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state variables
if 'data' not in st.session_state:
    st.session_state.data = None
if 'filtered_data' not in st.session_state:
    st.session_state.filtered_data = None
if 'column_mapping' not in st.session_state:
    st.session_state.column_mapping = None
if 'outstanding_items' not in st.session_state:
    st.session_state.outstanding_items = []
if 'deficiencies' not in st.session_state:
    st.session_state.deficiencies = []
if 'changes_made' not in st.session_state:
    st.session_state.changes_made = False


def detect_column_mapping(df):
    """Auto-detect column names and map to standard names."""
    columns = [col.lower().strip() for col in df.columns]
    mapping = {}

    patterns = {
        'id': ['id', 'number', 'no', '#', 'item no'],
        'activity': ['activity', 'test', 'task', 'description', 'item', 'work'],
        'system': ['system', 'discipline', 'category', 'area', 'subsystem'],
        'phase': ['phase', 'stage', 'milestone'],
        'status': ['status', 'state', 'progress'],
        'priority': ['priority', 'importance', 'criticality'],
        'contractor': ['contractor', 'vendor', 'responsible', 'assignee'],
        'issues': ['issue', 'deficiency', 'defect', 'problem', 'nc', 'nonconformance'],
        'due_date': ['due', 'target', 'planned', 'schedule'],
        'completion_date': ['completion', 'complete', 'actual', 'finished'],
        'notes': ['notes', 'comments', 'remarks', 'observations']
    }

    for standard_name, keywords in patterns.items():
        for col_idx, col_name in enumerate(columns):
            original_col = df.columns[col_idx]
            if any(keyword in col_name for keyword in keywords):
                if standard_name not in mapping:
                    mapping[standard_name] = original_col
                    break

    return mapping


def load_data(file):
    """Load T&C checklist from Excel file."""
    try:
        xls = pd.ExcelFile(file)

        if len(xls.sheet_names) > 1:
            st.info(f"Found {len(xls.sheet_names)} sheets: {', '.join(xls.sheet_names)}")
            sheet_name = st.selectbox("Select sheet to load:", xls.sheet_names, key="sheet_selector")
        else:
            sheet_name = 0

        df = pd.read_excel(file, sheet_name=sheet_name)
        df.columns = df.columns.str.strip()

        # Add unique ID if missing
        if 'ID' not in df.columns and 'id' not in [c.lower() for c in df.columns]:
            df.insert(0, 'ID', range(1, len(df) + 1))

        mapping = detect_column_mapping(df)

        # Add default status if missing
        if 'status' not in mapping:
            st.warning("Status column not found. Adding default status column.")
            df['Status'] = 'Not Started'
            mapping['status'] = 'Status'

        return df, mapping

    except Exception as e:
        st.error(f"Error loading file: {str(e)}")
        return None, None


def save_data_to_excel(df, filename="tc_checklist_updated.xlsx"):
    """Save dataframe with outstanding items and deficiencies to Excel."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='T&C Checklist')

        # Outstanding items
        if st.session_state.outstanding_items:
            outstanding_df = pd.DataFrame(st.session_state.outstanding_items)
            outstanding_df.to_excel(writer, index=False, sheet_name='Outstanding Items')

        # Deficiencies
        if st.session_state.deficiencies:
            deficiencies_df = pd.DataFrame(st.session_state.deficiencies)
            deficiencies_df.to_excel(writer, index=False, sheet_name='Deficiencies')

    output.seek(0)
    return output


def filter_data(df, mapping, filters):
    """Apply filters to dataframe."""
    filtered = df.copy()

    if mapping:
        for key in ['system', 'status', 'phase', 'contractor', 'priority']:
            if key in mapping and filters.get(key) and filters[key] != 'All':
                filtered = filtered[filtered[mapping[key]] == filters[key]]

    return filtered


def create_status_chart(df, mapping):
    """Create status distribution pie chart."""
    if 'status' not in mapping:
        return None

    status_col = mapping['status']
    status_counts = df[status_col].value_counts()

    color_map = {
        'completed': '#22c55e',
        'in progress': '#f59e0b',
        'not started': '#ef4444',
        'n/a': '#6b7280'
    }

    colors = [color_map.get(str(s).lower(), '#888888') for s in status_counts.index]

    fig = go.Figure(data=[go.Pie(
        labels=status_counts.index,
        values=status_counts.values,
        marker=dict(colors=colors),
        hole=0.4,
        textinfo='label+percent+value'
    )])
    fig.update_layout(
        title="T&C Status Distribution",
        height=400,
        showlegend=True
    )
    return fig


def create_phase_status_heatmap(df, mapping):
    """Create heatmap showing status by phase and system."""
    if not all(k in mapping for k in ['phase', 'system', 'status']):
        return None

    pivot = pd.crosstab([df[mapping['phase']], df[mapping['system']]], df[mapping['status']])

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns,
        y=[f"{p} - {s}" for p, s in pivot.index],
        colorscale='RdYlGn',
        text=pivot.values,
        texttemplate='%{text}',
        textfont={"size": 10}
    ))

    fig.update_layout(
        title="Status Distribution by Phase and System",
        xaxis_title="Status",
        yaxis_title="Phase - System",
        height=max(400, len(pivot) * 25)
    )
    return fig


def create_phase_progress_chart(df, mapping):
    """Create phase progress bar chart."""
    if 'phase' not in mapping or 'status' not in mapping:
        return None

    phase_col = mapping['phase']
    status_col = mapping['status']

    phase_data = []

    for phase in sorted(df[phase_col].dropna().unique(), key=str):
        phase_df = df[df[phase_col] == phase]
        total = len(phase_df)

        # Count each status explicitly
        completed = (phase_df[status_col] == 'Completed').sum()
        in_progress = (phase_df[status_col] == 'In Progress').sum()
        not_started = (phase_df[status_col] == 'Not Started').sum()
        na_items = (phase_df[status_col] == 'N/A').sum()

        phase_data.append({
            'Phase': str(phase),
            'Completed': completed,
            'In Progress': in_progress,
            'Not Started': not_started,
            'N/A': na_items,
            'Completion %': round(completed / total * 100, 1) if total > 0 else 0
        })


    phase_df = pd.DataFrame(phase_data)

    fig = go.Figure()
    fig.add_trace(go.Bar(name='Completed', x=phase_df['Phase'], y=phase_df['Completed'], marker_color='#22c55e'))
    fig.add_trace(go.Bar(name='In Progress', x=phase_df['Phase'], y=phase_df['In Progress'], marker_color='#f59e0b'))
    fig.add_trace(go.Bar(name='Not Started', x=phase_df['Phase'], y=phase_df['Not Started'], marker_color='#ef4444'))

    fig.update_layout(
        title="Phase Progress",
        xaxis_title="Phase",
        yaxis_title="Number of Activities",
        barmode='stack',
        height=400
    )
    return fig


def create_discipline_status_chart(df, mapping):
    """Create horizontal bar chart of statuses by system."""
    if 'system' not in mapping or 'status' not in mapping:
        return None

    system_status = pd.crosstab(df[mapping['system']], df[mapping['status']])

    fig = go.Figure()
    colors = {'Completed': '#22c55e', 'In Progress': '#f59e0b', 'Not Started': '#ef4444', 'N/A': '#6b7280'}

    for status in system_status.columns:
        color = colors.get(status, '#888888')
        fig.add_trace(go.Bar(
            name=status,
            y=system_status.index,
            x=system_status[status],
            orientation='h',
            marker=dict(color=color)
        ))

    fig.update_layout(
        title="Status by Discipline/System",
        xaxis_title="Number of Activities",
        yaxis_title="Discipline/System",
        barmode='stack',
        height=max(400, len(system_status) * 40)
    )
    return fig


def create_issues_trend_chart(df, mapping):
    """Create bar chart of total issues by system."""
    if 'issues' not in mapping:
        return None

    issues_col = mapping['issues']
    df_copy = df.copy()
    df_copy[issues_col] = pd.to_numeric(df_copy[issues_col], errors='coerce').fillna(0)

    if 'system' in mapping:
        system_col = mapping['system']
        issues_by_system = df_copy.groupby(system_col)[issues_col].sum().sort_values(ascending=True)

        fig = go.Figure(data=[go.Bar(
            x=issues_by_system.values,
            y=issues_by_system.index,
            orientation='h',
            marker=dict(color='#ef4444'),
            text=issues_by_system.values,
            textposition='auto'
        )])

        fig.update_layout(
            title="Total Issues by Discipline/System",
            xaxis_title="Number of Issues",
            yaxis_title="Discipline/System",
            height=max(400, len(issues_by_system) * 40)
        )
        return fig

    return None


def generate_summary_report(df, mapping):
    """Generate text report with overall status and issues summaries."""
    total = len(df)
    report = f"""
# T&C Comprehensive Summary Report
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Total Activities:** {total}

---

## 1. Overall Status Summary
"""

    # Status summary
    if 'status' in mapping:
        status_col = mapping['status']
        status_counts = df[status_col].value_counts()

        for status, count in status_counts.items():
            pct = (count / total * 100) if total > 0 else 0
            report += f"- **{status}:** {count} ({pct:.1f}%)\n"

    # Issues summary
    if 'issues' in mapping:
        issues_col = mapping['issues']
        df_copy = df.copy()
        df_copy[issues_col] = pd.to_numeric(df_copy[issues_col], errors='coerce').fillna(0)
        total_issues = int(df_copy[issues_col].sum())
        activities_with_issues = len(df_copy[df_copy[issues_col] > 0])
        report += f"\n**Total Issues/Deficiencies:** {total_issues}\n"
        report += f"**Activities with Issues:** {activities_with_issues}\n"

    # Status by phase
    if 'phase' in mapping and 'status' in mapping:
        report += "\n---\n\n## 2. Status by Phase\n"
        phase_col = mapping['phase']
        status_col = mapping['status']

        for phase in sorted(df[phase_col].dropna().unique(), key=str):
            phase_df = df[df[phase_col] == phase]
            report += f"\n### {phase}\n"
            phase_status = phase_df[status_col].value_counts()
            for status, count in phase_status.items():
                pct = (count / len(phase_df) * 100) if len(phase_df) > 0 else 0
                report += f"- {status}: {count} ({pct:.1f}%)\n"

    # Status by system
    if 'system' in mapping and 'status' in mapping:
        report += "\n---\n\n## 3. Status by Discipline/System\n"
        system_col = mapping['system']
        status_col = mapping['status']

    for system in sorted(df[system_col].dropna().unique(), key=str):
        system_df = df[df[system_col] == system]
        total_sys = len(system_df)

        completed = (system_df[status_col] == 'Completed').sum()
        in_progress = (system_df[status_col] == 'In Progress').sum()
        not_started = (system_df[status_col] == 'Not Started').sum()
        na_items = (system_df[status_col] == 'N/A').sum()

        # Completion % can be based on "real" tasks (excluding N/A)
        denom = total_sys - na_items
        pct = (completed / denom * 100) if denom > 0 else 0

        report += (
            f"- **{system}:** {completed}/{denom} completed "
            f"({pct:.1f}%) | In Progress: {in_progress}, "
            f"Not Started: {not_started}, N/A: {na_items}\n"
        )
 

    # Outstanding items log
    if st.session_state.outstanding_items:
        report += "\n---\n\n## 4. Outstanding Items Log\n"
        for i, item in enumerate(st.session_state.outstanding_items, 1):
            status = item.get('status', 'Not Started')  # Default to "Not Started" if missing
            report += f"\n### Outstanding Item #{i}\n"
            report += f"- **Description:** {item.get('description', '')}\n"
            report += f"- **Related Activity:** {item.get('activity_name', 'N/A')}\n"
            report += f"- **Phase:** {item.get('phase', 'N/A')}\n"
            report += f"- **Priority:** {item.get('priority', 'N/A')}\n"
            report += f"- **Responsible:** {item.get('responsible', 'N/A')}\n"
            report += f"- **Due Date:** {item.get('due_date', 'N/A')}\n"
            report += f"- **Status:** {status}\n"

    # Deficiencies log
    if st.session_state.deficiencies:
        report += "\n---\n\n## 5. Deficiencies/Issues Log\n"
        for i, deficiency in enumerate(st.session_state.deficiencies, 1):
            report += f"\n### Deficiency #{i}\n"
            report += f"- **Description:** {deficiency.get('description', '')}\n"
            report += f"- **Related Activity:** {deficiency.get('activity_name', 'N/A')}\n"
            report += f"- **System:** {deficiency.get('system', 'N/A')}\n"
            report += f"- **Severity:** {deficiency.get('severity', 'N/A')}\n"
            report += f"- **Date Identified:** {deficiency.get('date_identified', 'N/A')}\n"
            report += f"- **Resolution Status:** {deficiency.get('resolution_status', 'Open')}\n"
            report += f"- **Resolution Date:** {deficiency.get('actual_resolution_date', 'N/A')}\n"

    # Critical open items summary
    if 'priority' in mapping and 'status' in mapping:
        priority_col = mapping['priority']
        status_col = mapping['status']

        # Critical items that are NOT completed
        critical_open = df[
            df[priority_col].str.lower().str.contains('critical', na=False) &
            (df[status_col] != 'Completed')
        ]

        if len(critical_open) > 0:
            report += "\n---\n\n## 6. ⚠️ Critical Open Items\n"
            if 'activity' in mapping:
                activity_col = mapping['activity']
                for _, row in critical_open.iterrows():
                    activity = row[activity_col]
                    phase = row[mapping['phase']] if 'phase' in mapping else 'N/A'
                    status = row[status_col] if pd.notna(row[status_col]) else 'N/A'
                    report += f"- **{activity}** (Phase: {phase}, Status: {status})\n"

    return report
  

def edit_activity_status(df, mapping, activity_id):
    """Edit status and details of a specific activity."""
    if 'id' in mapping:
        id_col = mapping['id']
        activity = df[df[id_col] == activity_id]
    else:
        if 0 <= activity_id < len(df):
            activity = df.iloc[activity_id:activity_id+1]
        else:
            st.error("Activity not found")
            return df

    if activity.empty:
        st.error("Activity not found")
        return df

    st.subheader(f"Edit Activity: {activity.iloc[0][mapping.get('activity', 'ID')]}")

    with st.form(f"edit_form_{activity_id}"):
        col1, col2 = st.columns(2)

        with col1:
            if 'status' in mapping:
                status_col = mapping['status']
                current_status = activity.iloc[0][status_col]

                # Updated status options
                options_status = ['Not Started', 'In Progress', 'Completed', 'N/A']

                # Default to first option if current_status not in list
                idx_status = options_status.index(current_status) if current_status in options_status else 0

                new_status = st.selectbox("Status", options=options_status, index=idx_status)
            

            if 'priority' in mapping:
                priority_col = mapping['priority']
                current_priority = activity.iloc[0][priority_col]
                options_priority = ['Critical', 'High', 'Medium', 'Low']
                idx_priority = options_priority.index(current_priority) if current_priority in options_priority else 2
                new_priority = st.selectbox("Priority", options=options_priority, index=idx_priority)

        with col2:
            if 'contractor' in mapping:
                contractor_col = mapping['contractor']
                new_contractor = st.text_input("Contractor/Responsible", value=str(activity.iloc[0][contractor_col]))

            if 'completion_date' in mapping:
                mapping_comp = mapping['completion_date']
                current_date = activity.iloc[0][mapping_comp]
                if pd.isna(current_date):
                    current_date = None
                else:
                    try:
                        current_date = pd.to_datetime(current_date)
                    except Exception:
                        current_date = None
                new_completion = st.date_input("Completion Date", value=current_date)

        new_issues = 0
        if 'issues' in mapping:
            issues_col = mapping['issues']
            current_issues = activity.iloc[0][issues_col]
            try:
                current_issues = int(current_issues)
            except Exception:
                current_issues = 0
            new_issues = st.number_input("Number of Issues", min_value=0, value=current_issues)

        new_notes = ""
        if 'notes' in mapping:
            notes_col = mapping['notes']
            current_notes = activity.iloc[0][notes_col] if pd.notna(activity.iloc[0][notes_col]) else ""
            new_notes = st.text_area("Notes/Comments", value=current_notes)

        submitted = st.form_submit_button("Save Changes")

        if submitted:
            if 'id' in mapping:
                idx = df[df[id_col] == activity_id].index[0]
            else:
                idx = activity_id

            if 'status' in mapping:
                df.at[idx, status_col] = new_status
            if 'priority' in mapping:
                df.at[idx, priority_col] = new_priority
            if 'contractor' in mapping:
                df.at[idx, contractor_col] = new_contractor
            if 'completion_date' in mapping and new_completion:
                df.at[idx, mapping['completion_date']] = new_completion
            if 'issues' in mapping:
                df.at[idx, issues_col] = new_issues
            if 'notes' in mapping:
                df.at[idx, notes_col] = new_notes

            st.session_state.changes_made = True
            st.success("✅ Changes saved!")
            st.experimental_rerun()

    return df


def main():
    st.markdown('<p class="main-header">⚡ T&C Tracker - Full Management System</p>', unsafe_allow_html=True)

    # Sidebar - upload and filters
    with st.sidebar:
        st.header("📁 Data Management")

        uploaded_file = st.file_uploader("Upload T&C Checklist", type=['xlsx', 'xls'], help="Upload your Excel T&C checklist")

        if uploaded_file:
            data, mapping = load_data(uploaded_file)
            if data is not None:
                st.session_state.data = data
                st.session_state.column_mapping = mapping
                st.success(f"✅ Loaded {len(data)} activities")

                with st.expander("🔍 Detected Columns"):
                    if mapping:
                        for standard, actual in mapping.items():
                            st.write(f"**{standard.replace('_', ' ').title()}:** {actual}")

        st.divider()

        # Save/export button
        if st.session_state.data is not None:
            st.header("💾 Save & Export")
            if st.session_state.changes_made:
                st.warning("⚠️ You have unsaved changes")
            excel_file = save_data_to_excel(st.session_state.data)
            st.download_button(
                label="📥 Download Complete Checklist (Excel)",
                data=excel_file,
                file_name=f"tc_checklist_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        st.divider()

        # Filters
        if st.session_state.data is not None and st.session_state.column_mapping:
            st.header("🔍 Filters")
            df = st.session_state.data
            mapping = st.session_state.column_mapping
            filters = {}

            for key in ['phase', 'system', 'status', 'contractor', 'priority']:
                if key in mapping:
                    unique_vals = sorted([str(v) for v in df[mapping[key]].dropna().unique()])
                    filters[key] = st.selectbox(key.replace('_', ' ').title(), ['All'] + unique_vals, key=f"filter_{key}")

            st.session_state.filtered_data = filter_data(df, mapping, filters)

    # Main area
    if st.session_state.data is None:
        st.info("👈 Please upload your T&C checklist to get started")
        st.markdown("""
        ### 🎯 Key Features
        - ✏️ Edit activity statuses (Completed, In Progress, Not Started, N/A)
        - 📝 Track outstanding items
        - 🔧 Log deficiencies/issues
        - 🔍 Filter by phase, discipline, status
        - 📊 Real-time dashboards
        - 📈 Advanced visualizations
        - 📄 Comprehensive reporting
        - 💾 Export complete data
        """)
        return

    # Tabs for main features
    df = st.session_state.filtered_data if st.session_state.filtered_data is not None else st.session_state.data
    mapping = st.session_state.column_mapping

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📊 Dashboard",
        "✏️ Edit Activities",
        "📋 Outstanding Items",
        "🔧 Deficiencies",
        "📈 Analytics",
        "📄 Reports",
        "📑 Details"
    ])

    with tab1:
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Activities", len(df))

        with col2:
                if 'status' in mapping:
                    status_col = mapping['status']

                    total = len(df)
                    completed = (df[status_col] == 'Completed').sum()
                    na_items = (df[status_col] == 'N/A').sum()

                    # Exclude N/A from denominator so completion % is based on real tasks
                    denom = total - na_items
                    pct = (completed / denom * 100) if denom > 0 else 0

                    st.metric("Completed", completed, f"{pct:.1f}%")

        with col3:
            if 'status' in mapping:
                status_col = mapping['status']
                in_progress = (df[status_col] == 'In Progress').sum()
                st.metric("In Progress", in_progress)

        with col4:
            if 'issues' in mapping:
                issues_col = mapping['issues']
                df_copy = df.copy()
                df_copy[issues_col] = pd.to_numeric(df_copy[issues_col], errors='coerce').fillna(0)
                total_issues = int(df_copy[issues_col].sum())
                st.metric("Total Issues", total_issues)

        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            fig = create_status_chart(df, mapping)
            if fig:
                st.plotly_chart(fig, use_container_width=True)

            fig2 = create_phase_progress_chart(df, mapping)
            if fig2:
                st.plotly_chart(fig2, use_container_width=True)

        with col2:
            fig3 = create_discipline_status_chart(df, mapping)
            if fig3:
                st.plotly_chart(fig3, use_container_width=True)

            fig4 = create_issues_trend_chart(df, mapping)
            if fig4:
                st.plotly_chart(fig4, use_container_width=True)

        fig_heatmap = create_phase_status_heatmap(df, mapping)
        if fig_heatmap:
            st.plotly_chart(fig_heatmap, use_container_width=True)

    with tab2:
        st.subheader("✏️ Edit T&C Activities")

        if 'activity' in mapping:
            activity_col = mapping['activity']
            search = st.text_input("🔎 Search activity to edit", "")
            search_results = df[df[activity_col].astype(str).str.contains(search, case=False, na=False)] if search else df

            if len(search_results) > 0:
                if 'id' in mapping:
                    id_col = mapping['id']
                    display_options = [f"{row[id_col]} - {row[activity_col]}" for _, row in search_results.iterrows()]
                    selected = st.selectbox("Select activity to edit:", display_options)
                    if selected:
                        activity_id = search_results.iloc[display_options.index(selected)][id_col]
                        st.session_state.data = edit_activity_status(st.session_state.data, mapping, activity_id)
                else:
                    display_options = [f"{idx} - {row[activity_col]}" for idx, row in search_results.iterrows()]
                    selected = st.selectbox("Select activity to edit:", display_options)
                    if selected:
                        activity_idx = int(selected.split(' - ')[0])
                        st.session_state.data = edit_activity_status(st.session_state.data, mapping, activity_idx)
            else:
                st.info("No activities found matching your search")

        st.divider()

        # Bulk status update
        st.subheader("Bulk Status Update")
        col1, col2, col3 = st.columns(3)

        bulk_phase = st.selectbox("Select Phase", ['All'] + sorted([str(p) for p in df[mapping['phase']].dropna().unique()]) if 'phase' in mapping else ['All'], key="bulk_phase")
        bulk_system = st.selectbox("Select Discipline", ['All'] + sorted([str(s) for s in df[mapping['system']].dropna().unique()]) if 'system' in mapping else ['All'], key="bulk_system")
        bulk_new_status = st.selectbox("New Status", ['Completed', 'In Progress', 'Not Started', 'N/A'], key="bulk_status")

        if st.button("Apply Bulk Update"):
            bulk_df = st.session_state.data.copy()
            mask = pd.Series(True, index=bulk_df.index)

            if 'phase' in mapping and bulk_phase != 'All':
                mask &= bulk_df[mapping['phase']] == bulk_phase
            if 'system' in mapping and bulk_system != 'All':
                mask &= bulk_df[mapping['system']] == bulk_system

            if 'status' in mapping:
                bulk_df.loc[mask, mapping['status']] = bulk_new_status
                st.session_state.data = bulk_df
                st.session_state.changes_made = True
                st.success(f"✅ Updated {mask.sum()} activities to '{bulk_new_status}'")
                st.experimental_rerun()

    # Tabs 3 to 7 (Outstanding items, Deficiencies, Analytics, Reports, Details)
    # Due to length, only this cleaned structure is shown. Full implementations can be added similarly.

    with tab3:
        st.subheader("📋 Outstanding Items Log")

        if st.session_state.data is None or st.session_state.column_mapping is None:
            st.info("Upload data first to track outstanding items.")
        else:
            activity_col = st.session_state.column_mapping.get('activity')
            df = st.session_state.data

            # Add new outstanding item form
            st.markdown("### Add New Outstanding Item")
            with st.form("form_new_outstanding"):
                selected_activity = st.selectbox(
                    "Select Related Activity",
                    options=df[activity_col].unique() if activity_col else [],
                    key="new_outstanding_activity"
                )
                description = st.text_area("Description of Outstanding Item")
                phase = st.text_input("Phase (optional)")
                priority = st.selectbox("Priority", options=["Low", "Medium", "High", "Critical"], index=2)
                responsible = st.text_input("Responsible Person/Contractor")
                due_date = st.date_input("Due Date", value=None)
                status = st.selectbox("Status", options=["Completed", "In Progress", "Not Started", "N/A"], index=0)

                submitted = st.form_submit_button("Add Outstanding Item")

                if submitted:
                    new_outstanding = {
                        "activity_name": selected_activity,
                        "description": description,
                        "phase": phase,
                        "priority": priority,
                        "responsible": responsible,
                        "due_date": str(due_date) if due_date else "",
                        "status": status
                    }
                    st.session_state.outstanding_items.append(new_outstanding)
                    st.success("Outstanding item added and tied to the selected activity!")

            st.divider()

            # Display outstanding items with filter by activity
            st.markdown("### Outstanding Items List")

            if len(st.session_state.outstanding_items) == 0:
                st.info("No outstanding items recorded yet.")
            else:
                filter_activity = st.selectbox(
                    "Filter Outstanding Items by Activity",
                    options=["All"] + sorted(set(item['activity_name'] for item in st.session_state.outstanding_items)),
                    key="filter_outstanding_activity"
                )
                filtered_items = st.session_state.outstanding_items
                if filter_activity != "All":
                    filtered_items = [item for item in filtered_items if item['activity_name'] == filter_activity]

                for idx, item in enumerate(filtered_items):
                    with st.expander(f"Outstanding Item #{idx+1} (Activity: {item['activity_name']})"):
                        st.write(f"**Description:** {item['description']}")
                        st.write(f"**Phase:** {item.get('phase', '')}")
                        st.write(f"**Priority:** {item.get('priority', '')}")
                        st.write(f"**Responsible:** {item.get('responsible', '')}")
                        st.write(f"**Due Date:** {item.get('due_date', '')}")
                        st.write(f"**Status:** {item.get('status', '')}")

                        # Optionally add edit or delete functionality here

    with tab4:
        st.subheader("🔧 Deficiencies/Issues Log")

        if st.session_state.data is None or st.session_state.column_mapping is None:
            st.info("Upload data first to track deficiencies.")
        else:
            activity_col = st.session_state.column_mapping.get('activity')
            df = st.session_state.data

            # Add new deficiency form
            st.markdown("### Add New Deficiency / Issue")
            with st.form("form_new_deficiency"):
                selected_activity = st.selectbox(
                    "Select Related Activity",
                    options=df[activity_col].unique() if activity_col else [],
                    key="new_deficiency_activity"
                )
                description = st.text_area("Deficiency Description")
                system = st.text_input("System/Discipline (optional)")
                severity = st.selectbox("Severity", options=["Low", "Medium", "High", "Critical"], index=2)
                date_identified = st.date_input("Date Identified", value=None)
                resolution_status = st.selectbox("Resolution Status", options=["Open", "In Progress", "Resolved", "Closed"], index=0)
                actual_resolution_date = st.date_input("Resolution Date (if resolved)", value=None)

                submitted = st.form_submit_button("Add Deficiency")

                if submitted:
                    new_deficiency = {
                        "activity_name": selected_activity,
                        "description": description,
                        "system": system,
                        "severity": severity,
                        "date_identified": str(date_identified) if date_identified else "",
                        "resolution_status": resolution_status,
                        "actual_resolution_date": str(actual_resolution_date) if actual_resolution_date else ""
                    }
                    st.session_state.deficiencies.append(new_deficiency)
                    st.success("Deficiency added and tied to the selected activity!")

            st.divider()

            # Display deficiencies with filter by activity
            st.markdown("### Deficiency List")

            if len(st.session_state.deficiencies) == 0:
                st.info("No deficiencies recorded yet.")
            else:
                filter_activity = st.selectbox(
                    "Filter Deficiencies by Activity",
                    options=["All"] + sorted(set(item['activity_name'] for item in st.session_state.deficiencies)),
                    key="filter_deficiency_activity"
                )
                filtered_defs = st.session_state.deficiencies
                if filter_activity != "All":
                    filtered_defs = [item for item in filtered_defs if item['activity_name'] == filter_activity]

                for idx, item in enumerate(filtered_defs):
                    with st.expander(f"Deficiency #{idx+1} (Activity: {item['activity_name']})"):
                        st.write(f"**Description:** {item['description']}")
                        st.write(f"**System:** {item.get('system', '')}")
                        st.write(f"**Severity:** {item.get('severity', '')}")
                        st.write(f"**Date Identified:** {item.get('date_identified', '')}")
                        st.write(f"**Resolution Status:** {item.get('resolution_status', '')}")
                        st.write(f"**Resolution Date:** {item.get('actual_resolution_date', '')}")

                        # Optionally add edit or delete functionality here

    with tab5:
            st.subheader("📈 Advanced Analytics")
            
            # Analytics tabs
            analysis_tab1, analysis_tab2, analysis_tab3 = st.tabs(["Completion Analysis", "Issue Analysis", "Contractor Performance"])
            
            with analysis_tab1:
                col1, col2 = st.columns(2)
                
                with col1:
                    # Overall progress gauge
                    if 'status' in mapping:
                        status_col = mapping['status']
                        total = len(df)
                        completed = (df[status_col] == 'Completed').sum()
                        na_items = (df[status_col] == 'N/A').sum()

                        denom = total - na_items
                        completion_rate = (completed / denom * 100) if denom > 0 else 0
                        
                        fig = go.Figure(go.Indicator(
                            mode="gauge+number+delta",
                            value=completion_rate,
                            domain={'x': [0, 1], 'y': [0, 1]},
                            title={'text': "Overall Completion Rate (%)"},
                            delta={'reference': 100},
                            gauge={
                                'axis': {'range': [None, 100]},
                                'bar': {'color': "#22c55e"},
                                'steps': [
                                    {'range': [0, 50], 'color': "#fecaca"},
                                    {'range': [50, 75], 'color': "#fed7aa"},
                                    {'range': [75, 100], 'color': "#bbf7d0"}
                                ],
                                'threshold': {
                                    'line': {'color': "red", 'width': 4},
                                    'thickness': 0.75,
                                    'value': 90
                                }
                            }
                        ))
                        
                        fig.update_layout(height=400)
                        st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    # Phase completion comparison
                    if 'phase' in mapping and 'status' in mapping:
                        phase_col = mapping['phase']
                        status_col = mapping['status']
                        
                        phase_completion = []
                        for phase in sorted(df[phase_col].dropna().unique(), key=str):
                            phase_df = df[df[phase_col] == phase]
                            total = len(phase_df)
                            completed = (phase_df[status_col] == 'Completed').sum()
                            na_items = (phase_df[status_col] == 'N/A').sum()

                            denom = total - na_items
                            pct = (completed / denom * 100) if denom > 0 else 0

                            phase_completion.append({
                                'Phase': str(phase),
                                'Completion %': pct
                            })
                        
                        phase_df = pd.DataFrame(phase_completion)
                        
                        fig = px.bar(phase_df, x='Phase', y='Completion %',
                                   title="Completion Rate by Phase",
                                   color='Completion %',
                                   color_continuous_scale='RdYlGn')
                        fig.update_layout(height=400)
                        st.plotly_chart(fig, use_container_width=True)
                
                # Timeline analysis
                if 'due_date' in mapping and 'completion_date' in mapping:
                    st.subheader("Schedule Performance")
                    
                    due_col = mapping['due_date']
                    comp_col = mapping['completion_date']
                    
                    completed_df = df[df[comp_col].notna()].copy()
                    completed_df[due_col] = pd.to_datetime(completed_df[due_col], errors='coerce')
                    completed_df[comp_col] = pd.to_datetime(completed_df[comp_col], errors='coerce')
                    
                    on_time = len(completed_df[completed_df[comp_col] <= completed_df[due_col]])
                    late = len(completed_df[completed_df[comp_col] > completed_df[due_col]])
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Completed On Time", on_time)
                    with col2:
                        st.metric("Completed Late", late)
                    with col3:
                        on_time_pct = (on_time / len(completed_df) * 100) if len(completed_df) > 0 else 0
                        st.metric("On-Time Rate", f"{on_time_pct:.1f}%")
            
            with analysis_tab2:
                if 'issues' in mapping:
                    issues_col = mapping['issues']
                    df_copy = df.copy()
                    df_copy[issues_col] = pd.to_numeric(df_copy[issues_col], errors='coerce').fillna(0)
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Issues by severity (from deficiencies log)
                        if st.session_state.deficiencies:
                            severity_counts = {}
                            for def_item in st.session_state.deficiencies:
                                severity = def_item.get('severity', 'Unknown')
                                severity_counts[severity] = severity_counts.get(severity, 0) + 1
                            
                            fig = go.Figure(data=[go.Pie(
                                labels=list(severity_counts.keys()),
                                values=list(severity_counts.values()),
                                marker=dict(colors=['#dc2626', '#f59e0b', '#fbbf24'])
                            )])
                            fig.update_layout(title="Deficiencies by Severity", height=400)
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("No deficiencies logged yet")
                    
                    with col2:
                        # Resolution status of deficiencies
                        if st.session_state.deficiencies:
                            status_counts = {}
                            for def_item in st.session_state.deficiencies:
                                status = def_item.get('resolution_status', 'Unknown')
                                status_counts[status] = status_counts.get(status, 0) + 1
                            
                            fig = go.Figure(data=[go.Bar(
                                x=list(status_counts.keys()),
                                y=list(status_counts.values()),
                                marker_color=['#ef4444', '#f59e0b', '#22c55e', '#10b981']
                            )])
                            fig.update_layout(title="Deficiency Resolution Status", height=400)
                            st.plotly_chart(fig, use_container_width=True)
                    
                    # Top activities with issues
                    if 'activity' in mapping:
                        activity_col = mapping['activity']
                        top_issues = df_copy[df_copy[issues_col] > 0].nlargest(10, issues_col)
                        
                        if len(top_issues) > 0:
                            fig = px.bar(top_issues, x=activity_col, y=issues_col,
                                       title="Top 10 Activities with Most Issues",
                                       labels={issues_col: "Number of Issues", activity_col: "Activity"})
                            fig.update_layout(xaxis_tickangle=-45, height=400)
                            st.plotly_chart(fig, use_container_width=True)
            
            with analysis_tab3:
                if 'contractor' in mapping and 'status' in mapping:
                    contractor_col = mapping['contractor']
                    status_col = mapping['status']
                    
                    # Contractor performance table
                    contractor_stats = []
                    for contractor in df[contractor_col].dropna().unique():
                        contractor_df = df[df[contractor_col] == contractor]
                        total = len(contractor_df)

                        completed = (contractor_df[status_col] == 'Completed').sum()
                        in_progress = (contractor_df[status_col] == 'In Progress').sum()
                        not_started = (contractor_df[status_col] == 'Not Started').sum()
                        na_items = (contractor_df[status_col] == 'N/A').sum()
                            
                        if 'issues' in mapping:
                            issues_col = mapping['issues']
                            contractor_df_copy = contractor_df.copy()
                            contractor_df_copy[issues_col] = pd.to_numeric(contractor_df_copy[issues_col], errors='coerce').fillna(0)
                            total_issues = int(contractor_df_copy[issues_col].sum())
                        else:
                            total_issues = 0
                            
                            completion_rate = (closed / total * 100) if total > 0 else 0
                            
                            contractor_stats.append({
                                'Contractor': str(contractor),
                                'Total Activities': total,
                                'Closed': closed,
                                'In Progress': in_progress,
                                'Completion %': round(completion_rate, 1),
                                'Total Issues': total_issues
                            })
                    
                    contractor_df = pd.DataFrame(contractor_stats).sort_values('Completion %', ascending=False)
                    
                    # Display table
                    st.dataframe(contractor_df, use_container_width=True, height=300)
                    
                    # Visualization
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        name='Completion %',
                        x=contractor_df['Contractor'],
                        y=contractor_df['Completion %'],
                        marker_color='#22c55e',
                        yaxis='y'
                    ))
                    fig.add_trace(go.Scatter(
                        name='Total Issues',
                        x=contractor_df['Contractor'],
                        y=contractor_df['Total Issues'],
                        marker_color='#ef4444',
                        yaxis='y2',
                        mode='lines+markers'
                    ))
                    
                    fig.update_layout(
                        title="Contractor Performance: Completion vs Issues",
                        xaxis_title="Contractor",
                        yaxis=dict(title="Completion %", side='left'),
                        yaxis2=dict(title="Total Issues", side='right', overlaying='y'),
                        height=400
                    )
                    st.plotly_chart(fig, use_container_width=True)

    with tab6:
        st.subheader("📄 Comprehensive Reports")
        report_text = generate_summary_report(df, mapping)
        st.markdown(report_text)

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="📥 Download Report (TXT)",
                data=report_text,
                file_name=f"tc_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain"
            )
        with col2:
            html_report = report_text.replace('\n', '<br>')
            st.download_button(
                label="📥 Download Report (HTML)",
                data=html_report,
                file_name=f"tc_report_{datetime.now().strftime('%Y%m%d_%H%M')}.html",
                mime="text/html"
            )

    with tab7:
        st.subheader("📑 Detailed Activity List")
        if 'activity' in mapping:
            activity_col = mapping['activity']
            search = st.text_input("🔎 Search activities", "", key="detail_search")
            if search:
                df = df[df[activity_col].astype(str).str.contains(search, case=False, na=False)]

        with st.expander("⚙️ Column Settings"):
            available_columns = df.columns.tolist()
            selected_columns = st.multiselect(
                "Select columns to display",
                options=available_columns,
                default=available_columns[:10] if len(available_columns) > 10 else available_columns
            )

        display_df = df[selected_columns] if selected_columns else df
        st.dataframe(display_df, use_container_width=True, height=600)

        col1, col2 = st.columns(2)
        with col1:
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Download Filtered Data (CSV)",
                data=csv,
                file_name=f"tc_data_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )
        with col2:
            json_data = df.to_json(orient='records', date_format='iso')
            st.download_button(
                label="📥 Download as JSON",
                data=json_data,
                file_name=f"tc_data_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                mime="application/json"
            )


if __name__ == "__main__":
    main()
