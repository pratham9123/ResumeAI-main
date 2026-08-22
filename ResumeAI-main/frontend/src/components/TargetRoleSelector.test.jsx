import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import TargetRoleSelector from './TargetRoleSelector'

function ControlledSelector() {
  const [value, setValue] = useState('software_engineer')
  return <TargetRoleSelector value={value} onChange={setValue} />
}

describe('TargetRoleSelector', () => {
  it('shows every supported role and updates the selection', async () => {
    const user = userEvent.setup()
    render(<ControlledSelector />)

    const selector = screen.getByLabelText('Target Role')
    expect(selector).toHaveValue('software_engineer')
    expect(screen.getAllByRole('option')).toHaveLength(6)

    await user.selectOptions(selector, 'machine_learning_engineer')
    expect(selector).toHaveValue('machine_learning_engineer')
  })
})
