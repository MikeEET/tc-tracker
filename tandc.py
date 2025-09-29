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
from datetime import datetime, timedelta
import io
from pathlib import Path
import json

# Page configuration
st.set_page_config(
    page_title="T&C Tracker",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
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

# Initialize session state
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
    """Auto-detect column names and create mapping to standard names"""
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
    """Load T&C checklist from Excel file"""
    try:
        xls = pd.ExcelFile(file)
        
        if len(xls.sheet_names) > 1:
            st.info(f"Found {len(xls.sheet_names)} sheets: {', '.join(xls.sheet_names)}")
            sheet_name = st.selectbox("Select sheet to load:", xls.sheet_names, key="sheet_selector")
        else:
            sheet_name = 0
        
        df = pd.read_excel(file, sheet_name=sheet_name)
        df.columns = df.columns.str.strip()
        
        # Add a unique ID column if not present
        if 'ID' not in df.columns and 'id' not in [c.lower() for c in df.columns]:
            df.insert(0, 'ID', range(1, len(df) + 1))
        
        mapping = detect_column_mapping(df)
        
        # Ensure status column exists
        if 'status' not in mapping:
            st.warning("Status column not found. Adding default status column.")
            df['Status'] = 'Open'
            mapping['status'] = 'Status'
        
        return df, mapping
    except Exception as e:
        st.error(f"Error loading file: {str(e)}")
        return None, None

def save_data_to_excel(df, filename="tc_checklist_updated.xlsx"):
    """Save dataframe to Excel file"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='T&C Checklist')
        
        # Save outstanding items
        if st.session_state.outstanding_items:
            outstanding_df = pd.DataFrame(st.session_state.outstanding_items)
            outstanding_df.to_excel(writer, index=False, sheet_name='Outstanding Items')
        
        # Save deficiencies
        if st.session_state.deficiencies:
            deficiencies_df = pd.DataFrame(st.session_state.deficiencies)
            deficiencies_df.to_excel(writer, index=False, sheet_name='Deficiencies')
    
    output.seek(0)
    return output

def filter_data(df, mapping, filters):
    """Apply multiple filters to dataframe"""
    filtered = df.copy()
    
    if mapping:
        if 'system' in mapping and filters.get('system') != 'All':
            filtered = filtered[filtered[mapping['system']] == filters['system']]
        if 'status' in mapping and filters.get('status') != 'All':
            filtered = filtered[filtered[mapping['status']] == filters['status']]
        if 'phase' in mapping and filters.get('phase') != 'All':
            filtered = filtered[filtered[mapping['phase']] == filters['phase']]
        if 'contractor' in mapping and filters.get('contractor') != 'All':
            filtered = filtered[filtered[mapping['contractor']] == filters['contractor']]
        if 'priority' in mapping and filters.get('priority') != 'All':
            filtered = filtered[filtered[mapping['priority']] == filters['priority']]
    
    return filtered

def create_status_chart(df, mapping):
    """Create status distribution chart"""
    if 'status' not in mapping:
        return None
    
    status_col = mapping['status']
    status_counts = df[status_col].value_counts()
    
    color_map = {
        'closed': '#22c55e',
        'complete': '#22c55e',
        'completed': '#22c55e',
        'in progress': '#f59e0b',
        'in-progress': '#f59e0b',
        'open': '#ef4444',
        'not started': '#ef4444',
        'n/a': '#6b7280',
        'na': '#6b7280'
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
    """Create heatmap showing status by phase and system"""
    if 'phase' not in mapping or 'system' not in mapping or 'status' not in mapping:
        return None
    
    phase_col = mapping['phase']
    system_col = mapping['system']
    status_col = mapping['status']
    
    # Create pivot table
    pivot = pd.crosstab([df[phase_col], df[system_col]], df[status_col])
    
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
    """Create phase progress chart"""
    if 'phase' not in mapping or 'status' not in mapping:
        return None
    
    phase_col = mapping['phase']
    status_col = mapping['status']
    
    # Calculate completion per phase
    phase_data = []
    for phase in sorted(df[phase_col].unique(), key=str):
        if pd.notna(phase):
            phase_df = df[df[phase_col] == phase]
            total = len(phase_df)
            closed_keywords = ['closed', 'complete', 'completed']
            closed = len(phase_df[phase_df[status_col].str.lower().isin(closed_keywords)])
            in_progress = len(phase_df[phase_df[status_col].str.lower().str.contains('progress', na=False)])
            open_items = total - closed - in_progress
            
            phase_data.append({
                'Phase': str(phase),
                'Closed': closed,
                'In Progress': in_progress,
                'Open': open_items,
                'Completion %': round(closed/total*100, 1) if total > 0 else 0
            })
    
    phase_df = pd.DataFrame(phase_data)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(name='Closed', x=phase_df['Phase'], y=phase_df['Closed'], marker_color='#22c55e'))
    fig.add_trace(go.Bar(name='In Progress', x=phase_df['Phase'], y=phase_df['In Progress'], marker_color='#f59e0b'))
    fig.add_trace(go.Bar(name='Open', x=phase_df['Phase'], y=phase_df['Open'], marker_color='#ef4444'))
    
    fig.update_layout(
        title="Phase Progress",
        xaxis_title="Phase",
        yaxis_title="Number of Activities",
        barmode='stack',
        height=400
    )
    return fig

def create_discipline_status_chart(df, mapping):
    """Create discipline/system status chart"""
    if 'system' not in mapping or 'status' not in mapping:
        return None
    
    system_col = mapping['system']
    status_col = mapping['status']
    
    system_status = pd.crosstab(df[system_col], df[status_col])
    
    fig = go.Figure()
    colors = {'Closed': '#22c55e', 'In Progress': '#f59e0b', 'Open': '#ef4444', 'N/A': '#6b7280'}
    
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
    """Create issues/deficiencies trend chart"""
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
    """Generate comprehensive text-based summary report"""
    total = len(df)
    
    report = f"""
# T&C Comprehensive Summary Report
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Total Activities:** {total}

---

## 1. Overall Status Summary
"""
    
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
    
    # By Phase
    if 'phase' in mapping and 'status' in mapping:
        report += "\n---\n\n## 2. Status by Phase\n"
        phase_col = mapping['phase']
        status_col = mapping['status']
        
        for phase in sorted(df[phase_col].unique(), key=str):
            if pd.notna(phase):
                phase_df = df[df[phase_col] == phase]
                report += f"\n### {phase}\n"
                
                phase_status = phase_df[status_col].value_counts()
                for status, count in phase_status.items():
                    pct = (count / len(phase_df) * 100) if len(phase_df) > 0 else 0
                    report += f"- {status}: {count} ({pct:.1f}%)\n"
    
    # By Discipline/System
    if 'system' in mapping and 'status' in mapping:
        report += "\n---\n\n## 3. Status by Discipline/System\n"
        system_col = mapping['system']
        status_col = mapping['status']
        
        for system in sorted(df[system_col].unique(), key=str):
            if pd.notna(system):
                system_df = df[df[system_col] == system]
                closed_keywords = ['closed', 'complete', 'completed']
                closed = len(system_df[system_df[status_col].str.lower().isin(closed_keywords)])
                total_sys = len(system_df)
                pct = (closed / total_sys * 100) if total_sys > 0 else 0
                report += f"- **{system}:** {closed}/{total_sys} closed ({pct:.1f}%)\n"
    
    # Outstanding Items
    if st.session_state.outstanding_items:
        report += "\n---\n\n## 4. Outstanding Items Log\n"
        for i, item in enumerate(st.session_state.outstanding_items, 1):
            report += f"\n### Outstanding Item #{i}\n"
            report += f"- **Description:** {item['description']}\n"
            report += f"- **Related Activity:** {item.get('activity', 'N/A')}\n"
            report += f"- **Phase:** {item.get('phase', 'N/A')}\n"
            report += f"- **Priority:** {item.get('priority', 'N/A')}\n"
            report += f"- **Responsible:** {item.get('responsible', 'N/A')}\n"
            report += f"- **Due Date:** {item.get('due_date', 'N/A')}\n"
            report += f"- **Status:** {item.get('status', 'Open')}\n"
    
    # Deficiencies
    if st.session_state.deficiencies:
        report += "\n---\n\n## 5. Deficiencies/Issues Log\n"
        for i, deficiency in enumerate(st.session_state.deficiencies, 1):
            report += f"\n### Deficiency #{i}\n"
            report += f"- **Description:** {deficiency['description']}\n"
            report += f"- **Related Activity:** {deficiency.get('activity', 'N/A')}\n"
            report += f"- **System:** {deficiency.get('system', 'N/A')}\n"
            report += f"- **Severity:** {deficiency.get('severity', 'N/A')}\n"
            report += f"- **Date Identified:** {deficiency.get('date_identified', 'N/A')}\n"
            report += f"- **Resolution Status:** {deficiency.get('resolution_status', 'Open')}\n"
            report += f"- **Resolution Date:** {deficiency.get('resolution_date', 'N/A')}\n"
    
    # Critical Items
    if 'priority' in mapping and 'status' in mapping:
        priority_col = mapping['priority']
        status_col = mapping['status']
        closed_keywords = ['closed', 'complete', 'completed']
        
        critical_open = df[
            (df[priority_col].str.lower().str.contains('critical', na=False)) & 
            (~df[status_col].str.lower().isin(closed_keywords))
        ]
        
        if len(critical_open) > 0:
            report += "\n---\n\n## 6. ⚠️ Critical Open Items\n"
            if 'activity' in mapping:
                activity_col = mapping['activity']
                for _, row in critical_open.iterrows():
                    activity = row[activity_col]
                    phase = row[mapping['phase']] if 'phase' in mapping else 'N/A'
                    report += f"- **{activity}** (Phase: {phase})\n"
    
    return report

def edit_activity_status(df, mapping, activity_id):
    """Edit status and details of a specific activity"""
    if 'id' in mapping:
        id_col = mapping['id']
        activity = df[df[id_col] == activity_id]
    else:
        activity = df.iloc[activity_id:activity_id+1]
    
    if len(activity) == 0:
        st.error("Activity not found")
        return df
    
    st.subheader(f"Edit Activity: {activity.iloc[0][mapping['activity']] if 'activity' in mapping else f'ID {activity_id}'}")
    
    with st.form(f"edit_form_{activity_id}"):
        col1, col2 = st.columns(2)
        
        with col1:
            if 'status' in mapping:
                status_col = mapping['status']
                current_status = activity.iloc[0][status_col]
                new_status = st.selectbox(
                    "Status",
                    options=['Open', 'In Progress', 'Closed', 'N/A'],
                    index=['Open', 'In Progress', 'Closed', 'N/A'].index(current_status) if current_status in ['Open', 'In Progress', 'Closed', 'N/A'] else 0
                )
            
            if 'priority' in mapping:
                priority_col = mapping['priority']
                current_priority = activity.iloc[0][priority_col]
                new_priority = st.selectbox(
                    "Priority",
                    options=['Critical', 'High', 'Medium', 'Low'],
                    index=['Critical', 'High', 'Medium', 'Low'].index(current_priority) if current_priority in ['Critical', 'High', 'Medium', 'Low'] else 2
                )
        
        with col2:
            if 'contractor' in mapping:
                contractor_col = mapping['contractor']
                new_contractor = st.text_input("Contractor/Responsible", value=str(activity.iloc[0][contractor_col]))
            
            if 'completion_date' in mapping:
                new_completion = st.date_input("Completion Date", value=None)
        
        if 'issues' in mapping:
            issues_col = mapping['issues']
            current_issues = activity.iloc[0][issues_col]
            new_issues = st.number_input("Number of Issues", min_value=0, value=int(current_issues) if pd.notna(current_issues) else 0)
        
        if 'notes' in mapping:
            notes_col = mapping['notes']
            current_notes = activity.iloc[0][notes_col] if pd.notna(activity.iloc[0][notes_col]) else ""
            new_notes = st.text_area("Notes/Comments", value=current_notes)
        
        submitted = st.form_submit_button("Save Changes")
        
        if submitted:
            # Update dataframe
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
            st.rerun()
    
    return df

# Main Application
def main():
    st.markdown('<p class="main-header">⚡ T&C Tracker - Full Management System</p>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("📁 Data Management")
        
        uploaded_file = st.file_uploader(
            "Upload T&C Checklist",
            type=['xlsx', 'xls'],
            help="Upload your Excel T&C checklist"
        )
        
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
        
        # Save/Export
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
            
            if 'phase' in mapping:
                phase_col = mapping['phase']
                unique_phases = sorted([str(p) for p in df[phase_col].unique() if pd.notna(p)], key=str)
                filters['phase'] = st.selectbox("Phase", ['All'] + unique_phases)
            
            if 'system' in mapping:
                system_col = mapping['system']
                unique_systems = sorted([str(s) for s in df[system_col].unique() if pd.notna(s)])
                filters['system'] = st.selectbox("Discipline/System", ['All'] + unique_systems)
            
            if 'status' in mapping:
                status_col = mapping['status']
                unique_status = sorted([str(s) for s in df[status_col].unique() if pd.notna(s)])
                filters['status'] = st.selectbox("Status", ['All'] + unique_status)
            
            if 'contractor' in mapping:
                contractor_col = mapping['contractor']
                unique_contractors = sorted([str(c) for c in df[contractor_col].unique() if pd.notna(c)])
                filters['contractor'] = st.selectbox("Contractor", ['All'] + unique_contractors)
            
            if 'priority' in mapping:
                priority_col = mapping['priority']
                unique_priorities = sorted([str(p) for p in df[priority_col].unique() if pd.notna(p)])
                filters['priority'] = st.selectbox("Priority", ['All'] + unique_priorities)
            
            st.session_state.filtered_data = filter_data(df, mapping, filters)
    
    # Main content
    if st.session_state.data is None:
        st.info("👈 Please upload your T&C checklist to get started")
        
        st.markdown("### 🎯 Key Features")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            - ✏️ **Edit activity statuses** (Open, Closed, In Progress, N/A)
            - 📝 **Track outstanding items**
            - 🔧 **Log deficiencies/issues**
            - 🔍 **Filter by phase, discipline, status**
            """)
        with col2:
            st.markdown("""
            - 📊 **Real-time dashboards**
            - 📈 **Advanced visualizations**
            - 📄 **Comprehensive reporting**
            - 💾 **Export complete data**
            """)
    else:
        df = st.session_state.filtered_data if st.session_state.filtered_data is not None else st.session_state.data
        mapping = st.session_state.column_mapping
        
        # Tabs
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
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Activities", len(df))
            
            with col2:
                if 'status' in mapping:
                    status_col = mapping['status']
                    closed_keywords = ['closed', 'complete', 'completed']
                    closed = len(df[df[status_col].str.lower().isin(closed_keywords)])
                    pct = (closed/len(df)*100) if len(df) > 0 else 0
                    st.metric("Closed", closed, f"{pct:.1f}%")
            
            with col3:
                if 'status' in mapping:
                    in_progress = len(df[df[status_col].str.lower().str.contains('progress', na=False)])
                    st.metric("In Progress", in_progress)
            
            with col4:
                if 'issues' in mapping:
                    issues_col = mapping['issues']
                    df_copy = df.copy()
                    df_copy[issues_col] = pd.to_numeric(df_copy[issues_col], errors='coerce').fillna(0)
                    total_issues = int(df_copy[issues_col].sum())
                    st.metric("Total Issues", total_issues)
            
            st.divider()
            
            # Charts
            col1, col2 = st.columns(2)
            
            with col1:
                fig = create_status_chart(df, mapping)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                
                fig = create_phase_progress_chart(df, mapping)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                fig = create_discipline_status_chart(df, mapping)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                
                fig = create_issues_trend_chart(df, mapping)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
            
            # Heatmap
            fig = create_phase_status_heatmap(df, mapping)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
        
        with tab2:
            st.subheader("✏️ Edit T&C Activities")
            
            # Search and select activity to edit
            if 'activity' in mapping:
                activity_col = mapping['activity']
                search = st.text_input("🔎 Search activity to edit", "")
                
                if search:
                    search_results = df[df[activity_col].astype(str).str.contains(search, case=False, na=False)]
                else:
                    search_results = df
                
                if len(search_results) > 0:
                    # Create a display column
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
            
            with col1:
                if 'phase' in mapping:
                    bulk_phase = st.selectbox("Select Phase", ['All'] + sorted([str(p) for p in df[mapping['phase']].unique() if pd.notna(p)]), key="bulk_phase")
            
            with col2:
                if 'system' in mapping:
                    bulk_system = st.selectbox("Select Discipline", ['All'] + sorted([str(s) for s in df[mapping['system']].unique() if pd.notna(s)]), key="bulk_system")
            
            with col3:
                bulk_new_status = st.selectbox("New Status", ['Open', 'In Progress', 'Closed', 'N/A'], key="bulk_status")
            
            if st.button("Apply Bulk Update"):
                bulk_df = st.session_state.data.copy()
                mask = pd.Series([True] * len(bulk_df))
                
                if 'phase' in mapping and bulk_phase != 'All':
                    mask &= (bulk_df[mapping['phase']] == bulk_phase)
                if 'system' in mapping and bulk_system != 'All':
                    mask &= (bulk_df[mapping['system']] == bulk_system)
                
                if 'status' in mapping:
                    bulk_df.loc[mask, mapping['status']] = bulk_new_status
                    count = mask.sum()
                    st.session_state.data = bulk_df
                    st.session_state.changes_made = True
                    st.success(f"✅ Updated {count} activities to '{bulk_new_status}'")
                    st.rerun()
        
        with tab3:
            st.subheader("📋 Outstanding Items Log")
            
            # Add new outstanding item
            with st.expander("➕ Add New Outstanding Item"):
                with st.form("outstanding_form"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        out_description = st.text_area("Description*", height=100)
                        out_activity = st.text_input("Related Activity")
                        out_phase = st.text_input("Phase")
                    
                    with col2:
                        out_priority = st.selectbox("Priority", ['Critical', 'High', 'Medium', 'Low'])
                        out_responsible = st.text_input("Responsible Party")
                        out_due_date = st.date_input("Due Date")
                        out_status = st.selectbox("Status", ['Open', 'In Progress', 'Closed'])
                    
                    out_notes = st.text_area("Additional Notes")
                    
                    submitted = st.form_submit_button("Add Outstanding Item")
                    
                    if submitted and out_description:
                        outstanding_item = {
                            'id': len(st.session_state.outstanding_items) + 1,
                            'description': out_description,
                            'activity': out_activity,
                            'phase': out_phase,
                            'priority': out_priority,
                            'responsible': out_responsible,
                            'due_date': str(out_due_date),
                            'status': out_status,
                            'notes': out_notes,
                            'date_created': datetime.now().strftime('%Y-%m-%d %H:%M')
                        }
                        st.session_state.outstanding_items.append(outstanding_item)
                        st.session_state.changes_made = True
                        st.success("✅ Outstanding item added!")
                        st.rerun()
            
            # Display outstanding items
            if st.session_state.outstanding_items:
                st.markdown(f"**Total Outstanding Items:** {len([item for item in st.session_state.outstanding_items if item.get('status') != 'Closed'])}")
                
                for i, item in enumerate(st.session_state.outstanding_items):
                    with st.expander(f"#{item['id']} - {item['description'][:50]}... - **{item['status']}**"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**Description:** {item['description']}")
                            st.write(f"**Related Activity:** {item.get('activity', 'N/A')}")
                            st.write(f"**Phase:** {item.get('phase', 'N/A')}")
                            st.write(f"**Priority:** {item.get('priority', 'N/A')}")
                        
                        with col2:
                            st.write(f"**Responsible:** {item.get('responsible', 'N/A')}")
                            st.write(f"**Due Date:** {item.get('due_date', 'N/A')}")
                            st.write(f"**Status:** {item.get('status', 'Open')}")
                            st.write(f"**Created:** {item.get('date_created', 'N/A')}")
                        
                        if item.get('notes'):
                            st.write(f"**Notes:** {item['notes']}")
                        
                        # Update status
                        new_status = st.selectbox(
                            "Update Status",
                            ['Open', 'In Progress', 'Closed'],
                            index=['Open', 'In Progress', 'Closed'].index(item.get('status', 'Open')),
                            key=f"out_status_{i}"
                        )
                        
                        if st.button("Update", key=f"out_update_{i}"):
                            st.session_state.outstanding_items[i]['status'] = new_status
                            if new_status == 'Closed':
                                st.session_state.outstanding_items[i]['date_closed'] = datetime.now().strftime('%Y-%m-%d %H:%M')
                            st.session_state.changes_made = True
                            st.success("✅ Updated!")
                            st.rerun()
                        
                        if st.button("🗑️ Delete", key=f"out_delete_{i}"):
                            st.session_state.outstanding_items.pop(i)
                            st.session_state.changes_made = True
                            st.success("✅ Deleted!")
                            st.rerun()
            else:
                st.info("No outstanding items logged yet")
        
        with tab4:
            st.subheader("🔧 Deficiencies/Issues Log")
            
            # Add new deficiency
            with st.expander("➕ Add New Deficiency/Issue"):
                with st.form("deficiency_form"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        def_description = st.text_area("Description*", height=100)
                        def_activity = st.text_input("Related Activity")
                        def_system = st.text_input("System/Discipline")
                        def_severity = st.selectbox("Severity", ['Critical', 'Major', 'Minor'])
                    
                    with col2:
                        def_date_identified = st.date_input("Date Identified", value=datetime.now())
                        def_identified_by = st.text_input("Identified By")
                        def_contractor = st.text_input("Responsible Contractor")
                        def_resolution_status = st.selectbox("Resolution Status", ['Open', 'In Progress', 'Resolved', 'Closed'])
                    
                    def_corrective_action = st.text_area("Corrective Action Required")
                    def_resolution_date = st.date_input("Target Resolution Date")
                    
                    submitted = st.form_submit_button("Add Deficiency")
                    
                    if submitted and def_description:
                        deficiency = {
                            'id': len(st.session_state.deficiencies) + 1,
                            'description': def_description,
                            'activity': def_activity,
                            'system': def_system,
                            'severity': def_severity,
                            'date_identified': str(def_date_identified),
                            'identified_by': def_identified_by,
                            'contractor': def_contractor,
                            'resolution_status': def_resolution_status,
                            'corrective_action': def_corrective_action,
                            'target_resolution_date': str(def_resolution_date),
                            'actual_resolution_date': None,
                            'date_created': datetime.now().strftime('%Y-%m-%d %H:%M')
                        }
                        st.session_state.deficiencies.append(deficiency)
                        st.session_state.changes_made = True
                        st.success("✅ Deficiency logged!")
                        st.rerun()
            
            # Display deficiencies
            if st.session_state.deficiencies:
                # Summary metrics
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    total_def = len(st.session_state.deficiencies)
                    st.metric("Total Deficiencies", total_def)
                
                with col2:
                    open_def = len([d for d in st.session_state.deficiencies if d.get('resolution_status') not in ['Resolved', 'Closed']])
                    st.metric("Open", open_def)
                
                with col3:
                    critical_def = len([d for d in st.session_state.deficiencies if d.get('severity') == 'Critical'])
                    st.metric("Critical", critical_def)
                
                with col4:
                    resolved_def = len([d for d in st.session_state.deficiencies if d.get('resolution_status') in ['Resolved', 'Closed']])
                    st.metric("Resolved", resolved_def)
                
                st.divider()
                
                # Filter deficiencies
                def_filter = st.selectbox("Filter by Status", ['All', 'Open', 'In Progress', 'Resolved', 'Closed'])
                
                filtered_deficiencies = st.session_state.deficiencies
                if def_filter != 'All':
                    filtered_deficiencies = [d for d in st.session_state.deficiencies if d.get('resolution_status') == def_filter]
                
                for i, deficiency in enumerate(filtered_deficiencies):
                    actual_index = st.session_state.deficiencies.index(deficiency)
                    severity_color = {'Critical': '🔴', 'Major': '🟠', 'Minor': '🟡'}
                    
                    with st.expander(f"{severity_color.get(deficiency['severity'], '⚪')} Deficiency #{deficiency['id']} - {deficiency['description'][:50]}... - **{deficiency['resolution_status']}**"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**Description:** {deficiency['description']}")
                            st.write(f"**Related Activity:** {deficiency.get('activity', 'N/A')}")
                            st.write(f"**System:** {deficiency.get('system', 'N/A')}")
                            st.write(f"**Severity:** {deficiency.get('severity', 'N/A')}")
                            st.write(f"**Date Identified:** {deficiency.get('date_identified', 'N/A')}")
                        
                        with col2:
                            st.write(f"**Identified By:** {deficiency.get('identified_by', 'N/A')}")
                            st.write(f"**Responsible Contractor:** {deficiency.get('contractor', 'N/A')}")
                            st.write(f"**Resolution Status:** {deficiency.get('resolution_status', 'Open')}")
                            st.write(f"**Target Resolution:** {deficiency.get('target_resolution_date', 'N/A')}")
                            if deficiency.get('actual_resolution_date'):
                                st.write(f"**Actual Resolution:** {deficiency['actual_resolution_date']}")
                        
                        if deficiency.get('corrective_action'):
                            st.write(f"**Corrective Action:** {deficiency['corrective_action']}")
                        
                        # Update deficiency
                        st.markdown("---")
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            new_resolution_status = st.selectbox(
                                "Update Resolution Status",
                                ['Open', 'In Progress', 'Resolved', 'Closed'],
                                index=['Open', 'In Progress', 'Resolved', 'Closed'].index(deficiency.get('resolution_status', 'Open')),
                                key=f"def_status_{actual_index}"
                            )
                        
                        with col2:
                            if new_resolution_status in ['Resolved', 'Closed']:
                                resolution_date = st.date_input("Resolution Date", key=f"def_res_date_{actual_index}")
                        
                        with col3:
                            st.write("")
                            st.write("")
                            if st.button("Update", key=f"def_update_{actual_index}"):
                                st.session_state.deficiencies[actual_index]['resolution_status'] = new_resolution_status
                                if new_resolution_status in ['Resolved', 'Closed']:
                                    st.session_state.deficiencies[actual_index]['actual_resolution_date'] = str(resolution_date)
                                st.session_state.changes_made = True
                                st.success("✅ Updated!")
                                st.rerun()
                        
                        if st.button("🗑️ Delete Deficiency", key=f"def_delete_{actual_index}"):
                            st.session_state.deficiencies.pop(actual_index)
                            st.session_state.changes_made = True
                            st.success("✅ Deleted!")
                            st.rerun()
            else:
                st.info("No deficiencies logged yet")
        
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
                        closed_keywords = ['closed', 'complete', 'completed']
                        completion_rate = len(df[df[status_col].str.lower().isin(closed_keywords)]) / len(df) * 100 if len(df) > 0 else 0
                        
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
                        for phase in sorted(df[phase_col].unique(), key=str):
                            if pd.notna(phase):
                                phase_df = df[df[phase_col] == phase]
                                closed = len(phase_df[phase_df[status_col].str.lower().isin(closed_keywords)])
                                total = len(phase_df)
                                pct = (closed / total * 100) if total > 0 else 0
                                phase_completion.append({'Phase': str(phase), 'Completion %': pct})
                        
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
                    for contractor in df[contractor_col].unique():
                        if pd.notna(contractor):
                            contractor_df = df[df[contractor_col] == contractor]
                            total = len(contractor_df)
                            closed = len(contractor_df[contractor_df[status_col].str.lower().isin(['closed', 'complete', 'completed'])])
                            in_progress = len(contractor_df[contractor_df[status_col].str.lower().str.contains('progress', na=False)])
                            
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
                # Generate PDF-ready format (HTML)
                html_report = report_text.replace('\n', '<br>').replace('#', '<strong>').replace('</strong>', '</strong><br>')
                st.download_button(
                    label="📥 Download Report (HTML)",
                    data=html_report,
                    file_name=f"tc_report_{datetime.now().strftime('%Y%m%d_%H%M')}.html",
                    mime="text/html"
                )
        
        with tab7:
            st.subheader("📑 Detailed Activity List")
            
            # Search
            if 'activity' in mapping:
                activity_col = mapping['activity']
                search = st.text_input("🔎 Search activities", "", key="detail_search")
                if search:
                    df = df[df[activity_col].astype(str).str.contains(search, case=False, na=False)]
            
            # Show/hide columns
            with st.expander("⚙️ Column Settings"):
                available_columns = df.columns.tolist()
                selected_columns = st.multiselect(
                    "Select columns to display",
                    options=available_columns,
                    default=available_columns[:10] if len(available_columns) > 10 else available_columns
                )
            
            if selected_columns:
                display_df = df[selected_columns]
            else:
                display_df = df
            
            # Display dataframe
            st.dataframe(
                display_df,
                use_container_width=True,
                height=600
            )
            
            # Export options
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
                # JSON export
                json_data = df.to_json(orient='records', date_format='iso')
                st.download_button(
                    label="📥 Download as JSON",
                    data=json_data,
                    file_name=f"tc_data_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                    mime="application/json"
                )

if __name__ == "__main__":
    main()